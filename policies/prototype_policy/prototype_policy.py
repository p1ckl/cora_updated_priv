from policies.policy_base import PolicyBase
from policies.prototype_policy.prototype_policy_config import PrototypePolicyConfig  # Switch to your config type


class PrototypePolicy(PolicyBase):
    """
    A simple implementation of policy as a sample of how policies can be created.
    Refer to policy_base itself for more detailed descriptions of the method signatures.
    """
    def __init__(self, config : PrototypePolicyConfig):  # Switch to your config type
        super().__init__()
        pass

    def get_episode_runner(self):
        pass

    def compute_action(self, observation, task_action_count):
        pass

    def train(self, storage_buffer):
        pass

    def save(self, output_path_dir, task_id, task_total_steps):
        pass

    def load(self, model_path):
        pass
