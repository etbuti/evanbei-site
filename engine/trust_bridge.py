#!/usr/bin/env python3
import json

class TrustBridge:

    def __init__(self,
                 bridge_path="bridges/trust-bridges.json",
                 networks_path="networks"):

        self.bridges = json.load(open(bridge_path))["bridges"]
        self.networks_path = networks_path

    # ===== 获取网络配置 =====
    def load_network(self, network_id):
        path = f"{self.networks_path}/{network_id}.json"
        return json.load(open(path))

    # ===== 查找桥 =====
    def get_bridge(self, from_net, to_net):
        for b in self.bridges:
            if b["from_network"] == from_net and b["to_network"] == to_net:
                return b
        return None

    # ===== 判断节点是否接受 =====
    def accept_node(self, from_net, to_net, node_level):
        bridge = self.get_bridge(from_net, to_net)

        if not bridge:
            return False, 0.0

        if node_level not in bridge["accepted_levels"]:
            return False, 0.0

        return True, bridge.get("weight_multiplier", 1.0)

    # ===== 计算跨网络信任分 =====
    def effective_score(self, raw_score, multiplier):
        return raw_score * multiplier

    # ===== 验证签名来源 =====
    def verify_external_signature(self, signature_obj, local_network):

        node_net = signature_obj.get("network_id")
        node_level = signature_obj.get("level")

        accepted, weight = self.accept_node(
            from_net=local_network,
            to_net=node_net,
            node_level=node_level
        )

        return {
            "accepted": accepted,
            "weight": weight
        }
