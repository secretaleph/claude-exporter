"""
Tree builder for reconstructing conversation branches from messages.
"""
from collections import defaultdict
from typing import Any
from uuid import UUID

from .models import Branch, Conversation, ConversationTree, Message, MessageNode


class TreeBuilder:
    """Builds conversation tree structure from flat message list."""

    def __init__(self, conversation: Conversation):
        self.conversation = conversation
        self.messages = conversation.chat_messages

    def build_tree(self) -> ConversationTree:
        """
        Build complete conversation tree with all branches.

        Strategy:
        1. Group messages by index (messages with same index are siblings/branches)
        2. Build parent-child relationships based on temporal order and index
        3. Identify all unique paths through the tree (branches)
        """
        if not self.messages:
            return ConversationTree(
                conversation=self.conversation,
                root=None,
                all_messages=[],
                branches=[]
            )

        # Sort messages by created_at to get temporal order
        sorted_messages = sorted(self.messages, key=lambda m: m.created_at)

        # Group messages by index to find branches
        messages_by_index = defaultdict(list)
        for msg in sorted_messages:
            messages_by_index[msg.index].append(msg)

        # Build parent-child relationships
        self._build_parent_child_relationships(sorted_messages, messages_by_index)

        # Find root message (first human message, index 0)
        root_candidates = messages_by_index.get(0, [])
        if not root_candidates:
            # Fallback to first message
            root_message = sorted_messages[0]
        else:
            root_message = root_candidates[0]

        # Build tree structure
        root_node = self._build_message_node(root_message, set())

        # Extract all branch paths
        branches = self._extract_branches(root_node)

        # Find orphaned message chains
        orphaned_chains = self._find_orphaned_chains(sorted_messages, root_node)

        return ConversationTree(
            conversation=self.conversation,
            root=root_node,
            all_messages=sorted_messages,
            branches=branches,
            orphaned_chains=orphaned_chains
        )

    def _build_parent_child_relationships(
        self,
        sorted_messages: list[Message],
        messages_by_index: dict[int, list[Message]]
    ) -> None:
        """
        Build parent-child relationships between messages.

        The API data already contains parent_uuid values from the nested structure.
        This method preserves those relationships and builds the children arrays.

        Note: We used to reconstruct parent relationships from the index field,
        but this caused issues when indices had gaps, resulting in orphaned messages.
        Now we trust the API's parent_uuid values.
        """
        # Build a UUID -> Message lookup
        msg_by_uuid = {msg.uuid: msg for msg in sorted_messages}

        # Build children arrays based on existing parent_uuid values
        for msg in sorted_messages:
            if msg.parent_uuid:
                parent = msg_by_uuid.get(msg.parent_uuid)
                if parent:
                    parent.children.append(msg)

        # Note: parent_uuid values are already set from the API data
        # We don't need to compute them - they come from the nested structure

    def _build_message_node(self, message: Message, visited: set[UUID]) -> MessageNode:
        """
        Recursively build MessageNode tree structure.

        Args:
            message: Current message to build node for
            visited: Set of already visited message UUIDs to prevent cycles

        Returns:
            MessageNode with all children
        """
        if message.uuid in visited:
            # Prevent infinite loops
            return MessageNode(message=message, children=[])

        visited.add(message.uuid)

        children_nodes = []
        for child in message.children:
            child_node = self._build_message_node(child, visited)
            children_nodes.append(child_node)

        return MessageNode(message=message, children=children_nodes)

    def _extract_branches(self, root: MessageNode) -> list[list[UUID]]:
        """
        Extract all unique branch paths from the tree.

        A branch is a path from root to a leaf node.

        Returns:
            List of branch paths, where each path is a list of message UUIDs
        """
        branches = []

        def traverse(node: MessageNode, current_path: list[UUID]) -> None:
            # Add current message to path
            path = current_path + [node.message.uuid]

            if not node.children:
                # Leaf node - this is a complete branch
                branches.append(path)
            else:
                # Traverse all children
                for child in node.children:
                    traverse(child, path)

        traverse(root, [])
        return branches

    def extract_branch_objects(self, tree: ConversationTree | None = None) -> list[Branch]:
        """
        Extract all branches as Branch objects with metadata.

        Args:
            tree: Optional pre-built ConversationTree to use

        Returns:
            List of Branch objects representing each path through the conversation
        """
        if tree is None:
            tree = self.build_tree()

        if not tree.root:
            return []

        branches = []

        for idx, branch_path in enumerate(tree.branches):
            # Get messages for this branch
            messages = [
                msg for msg in tree.all_messages
                if msg.uuid in branch_path
            ]

            # Sort by index to maintain conversation order
            messages.sort(key=lambda m: m.index)

            # Determine where this branch diverges
            diverges_at = self._find_divergence_point(branch_path, tree.branches)

            branch = Branch(
                messages=messages,
                branch_id=f"branch-{idx + 1}",
                diverges_at_index=diverges_at,
                is_main=(idx == 0)  # First branch is considered main
            )
            branches.append(branch)

        return branches

    def _find_divergence_point(
        self,
        branch_path: list[UUID],
        all_branches: list[list[UUID]]
    ) -> int | None:
        """
        Find the index where this branch diverges from the main branch.

        Args:
            branch_path: The current branch path
            all_branches: All branch paths

        Returns:
            Index where divergence occurs, or None if this is the main branch
        """
        if not all_branches or branch_path == all_branches[0]:
            return None

        main_branch = all_branches[0]

        for idx, uuid in enumerate(branch_path):
            if idx >= len(main_branch) or uuid != main_branch[idx]:
                return idx

        return None

    def _find_orphaned_chains(
        self,
        all_messages: list[Message],
        root_node: MessageNode
    ) -> list[list[Message]]:
        """
        Find message chains that are orphaned (not connected to main tree).

        These typically occur when messages are regenerated or edited,
        leaving old versions in the database but not in the conversation path.

        Args:
            all_messages: All messages sorted by created_at
            root_node: Root of the main conversation tree

        Returns:
            List of orphaned message chains, each chain is a list of messages
        """
        # Collect all message UUIDs that are in the main tree
        messages_in_tree = set()

        def collect_tree_uuids(node: MessageNode) -> None:
            messages_in_tree.add(node.message.uuid)
            for child in node.children:
                collect_tree_uuids(child)

        collect_tree_uuids(root_node)

        # Find messages not in tree
        orphaned_messages = [m for m in all_messages if m.uuid not in messages_in_tree]

        if not orphaned_messages:
            return []

        # Build chains from orphaned messages
        # A chain starts with a message that has no parent or whose parent is also orphaned
        chains = []
        processed = set()

        for msg in orphaned_messages:
            if msg.uuid in processed:
                continue

            # Find the root of this orphaned chain
            chain_root = msg
            while chain_root.parent_uuid:
                parent = next((m for m in orphaned_messages if m.uuid == chain_root.parent_uuid), None)
                if parent:
                    chain_root = parent
                else:
                    break

            # Build chain from root
            if chain_root.uuid not in processed:
                chain = self._build_orphaned_chain(chain_root, orphaned_messages, processed)
                if chain:
                    chains.append(chain)

        return chains

    def _build_orphaned_chain(
        self,
        start_message: Message,
        orphaned_messages: list[Message],
        processed: set[UUID]
    ) -> list[Message]:
        """
        Build a linear chain starting from a message.

        Args:
            start_message: Starting message of the chain
            orphaned_messages: All orphaned messages
            processed: Set of already processed message UUIDs

        Returns:
            List of messages in the chain
        """
        chain = []
        current = start_message

        while current:
            if current.uuid in processed:
                break

            chain.append(current)
            processed.add(current.uuid)

            # Find next message in chain (first child)
            children = [m for m in orphaned_messages if m.parent_uuid == current.uuid]
            current = children[0] if children else None

        return chain
