"""
API client for Claude.ai unofficial API.
"""
from typing import Any

import cloudscraper
import browser_cookie3


class ClaudeAPIClient:
    """Client for interacting with Claude.ai unofficial API."""

    BASE_URL = "https://claude.ai/api"

    def __init__(self, session_key: str | None = None, cookies: dict[str, str] | None = None):
        """
        Initialize Claude API client.

        Args:
            session_key: Session key cookie value
            cookies: Full cookie dictionary (if session_key not provided)
        """
        if cookies:
            self.cookies = cookies
        elif session_key:
            self.cookies = {"sessionKey": session_key}
        else:
            # Try to extract from browser
            self.cookies = self._extract_cookies_from_browser()

        # Create cloudscraper session with more browser-like settings
        self.session = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'darwin',
                'mobile': False
            },
            delay=10  # Add delay for Cloudflare
        )

        # Set more complete browser-like headers
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://claude.ai/",
            "Origin": "https://claude.ai",
            "DNT": "1",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-CH-UA": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"macOS"',
        })

        # Set cookies
        for name, value in self.cookies.items():
            self.session.cookies.set(name, value, domain="claude.ai")

    def _extract_cookies_from_browser(self, domain: str = "claude.ai") -> dict[str, str]:
        """Extract session cookies from browser."""
        # Try different browsers in order
        for browser_fn_name, browser_fn in [
            ("Chrome", browser_cookie3.chrome),
            ("Firefox", browser_cookie3.firefox),
            ("Edge", browser_cookie3.edge),
            ("Safari", browser_cookie3.safari),
        ]:
            try:
                cookies = browser_fn(domain_name=domain)
                cookie_dict = {cookie.name: cookie.value for cookie in cookies}

                if "sessionKey" in cookie_dict:
                    return cookie_dict
            except Exception as e:
                continue

        raise ValueError(
            "Could not extract session cookies from browser. "
            "Please provide session_key with --session-key option.\n"
            "To get your session key:\n"
            "1. Open claude.ai in your browser\n"
            "2. Open DevTools (F12)\n"
            "3. Go to Application → Cookies → claude.ai\n"
            "4. Copy the 'sessionKey' value"
        )

    def get_organizations(self) -> list[dict[str, Any]]:
        """Get list of organizations the user belongs to."""
        url = f"{self.BASE_URL}/organizations"

        response = self.session.get(url, timeout=30.0)
        response.raise_for_status()
        return response.json()

    def get_conversations(self, org_id: str) -> list[dict[str, Any]]:
        """Get list of conversations for an organization."""
        url = f"{self.BASE_URL}/organizations/{org_id}/chat_conversations"

        response = self.session.get(url, timeout=30.0)
        response.raise_for_status()
        return response.json()

    def get_conversation(self, org_id: str, conversation_id: str) -> dict[str, Any]:
        """
        Get detailed conversation data including all messages.

        Args:
            org_id: Organization ID
            conversation_id: Conversation UUID

        Returns:
            Full conversation data with messages
        """
        url = f"{self.BASE_URL}/organizations/{org_id}/chat_conversations/{conversation_id}"

        response = self.session.get(url, timeout=30.0)
        response.raise_for_status()
        return response.json()

    def download_attachment(self, org_id: str, conversation_id: str, attachment_id: str) -> bytes:
        """
        Download an attachment from a conversation.

        Args:
            org_id: Organization ID
            conversation_id: Conversation UUID
            attachment_id: Attachment UUID

        Returns:
            Raw bytes of the attachment
        """
        url = f"{self.BASE_URL}/organizations/{org_id}/chat_conversations/{conversation_id}/attachments/{attachment_id}"

        response = self.session.get(url, timeout=60.0)
        response.raise_for_status()
        return response.content

    def get_default_org_id(self) -> str:
        """Get the default organization ID from cookies or API."""
        # Try to get from lastActiveOrg cookie first
        if "lastActiveOrg" in self.cookies:
            return self.cookies["lastActiveOrg"]

        # Fallback to API call
        orgs = self.get_organizations()
        if not orgs:
            raise ValueError("No organizations found")
        return orgs[0]["uuid"]
