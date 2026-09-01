    def _with_branch(self, body: dict[str, Any]) -> dict[str, Any]:
        """Add product_branch to a write body when one is configured.

        The orchestrator accepts it as a sibling of `payload` on every write
        endpoint. Returns a new dict so callers can reuse what they passed in.
        """
        if not self.product_branch:
            return body
        return {**body, "product_branch": self.product_branch}

