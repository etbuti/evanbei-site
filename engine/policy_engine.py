#!/usr/bin/env python3
import json
import time
import os

class PolicyEngine:

    def __init__(self, policy_path="policies/default.json"):
        self.policy = json.load(open(policy_path))

    # ===== Score =====
    def compute_score(self, heat, clusters, recency, anomaly):
        s = self.policy["scoring"]
        return (
            heat * s["heat_weight"]
            + clusters * s["cluster_weight"]
            + recency * s["recency_weight"]
            - anomaly * s["anomaly_penalty"]
        )

    # ===== Level =====
    def level_from_score(self, score, is_root=False):
        if is_root and self.policy["governance"].get("root_immutable", True):
            return "root"

        t = self.policy["thresholds"]

        if score >= t["core"]:
            return "core"
        if score >= t["trusted"]:
            return "trusted"
        if score >= t["watch"]:
            return "watch"
        if score >= t["suspicious"]:
            return "suspicious"

        return "revoked"

    # ===== Governance override =====
    def apply_governance(self, node_id, score, anomaly_count, is_root=False):

        level = self.level_from_score(score, is_root)

        if not is_root:
            g = self.policy["governance"]

            if anomaly_count >= g["anomaly_to_revoked"]:
                return "revoked"

            if anomaly_count >= g["anomaly_to_suspicious"]:
                return "suspicious"

        return level

    # ===== Dispatch =====
    def allowed_levels(self, task_type="normal"):
        return self.policy["dispatch"].get(task_type, [])

    # ===== Recency =====
    def recency_score(self, last_seen_ts):
        if not last_seen_ts:
            return 0

        age = time.time() - last_seen_ts
        return max(0, 1 - age / 86400)
