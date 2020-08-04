import os
import numpy as np
from pathlib import Path
from torch.utils.tensorboard.writer import SummaryWriter
from continual_rl.experiments.experiment import Experiment
from continual_rl.experiments.tasks.minigrid_task import MiniGridTask
from continual_rl.policies.ppo.ppo_policy_config import PPOPolicyConfig
from continual_rl.policies.ppo.ppo_policy import PPOPolicy


class TestPPOPolicy(object):

    def test_end_to_end_batch(self, set_tmp_directory, cleanup_experiment, request):
        """
        Not a unit test - a full (very short) run with PPO for a sanity check that it's working.
        This is testing: PPOPolicy, MiniGridTask, SummaryWriter
        """
        # Arrange
        experiment = Experiment(
            tasks=[MiniGridTask(action_space_id=0, env_spec='MiniGrid-Empty-8x8-v0', num_timesteps=10,
                                time_batch_size=1, eval_mode=False),
                   MiniGridTask(action_space_id=0, env_spec='MiniGrid-Unlock-v0', num_timesteps=10,
                                time_batch_size=1, eval_mode=False)
                   ])
        config = PPOPolicyConfig()

        # Make a subfolder of the output directory that only this experiment is using, to avoid conflict
        output_dir = Path(request.node.experiment_output_dir, "ppo_batch")
        os.makedirs(output_dir)
        experiment.set_output_dir(output_dir)
        config.set_output_dir(output_dir)

        policy = PPOPolicy(config, experiment.observation_size, experiment.action_spaces)
        summary_writer = SummaryWriter(log_dir=experiment.output_dir)

        # Act
        experiment.try_run(policy, summary_writer=summary_writer)

        # Assert
        assert Path(policy._config.output_dir, "core_process.log").is_file(), "Log file not created"
        assert np.any(['event' in file_name for file_name in os.listdir(experiment.output_dir)]), \
            "Summary writer file not created"
