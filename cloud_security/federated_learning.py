import numpy as np
import os
from django.conf import settings

class DDoSDetector:
    def __init__(self):
        self.normal_traffic_threshold = 100
    
    def detect_ddos(self, network_features):
        try:
            packet_count = float(network_features[0])
            byte_count = float(network_features[1])
            
            if packet_count > self.normal_traffic_threshold or byte_count > (self.normal_traffic_threshold * 100):
                return True
            return False
        except:
            return False