from abc import ABC
import numpy as np
import gym
from continual_rl.experiments.tasks.task_spec import TaskSpec


class TaskBase(ABC):
    def __init__(self, action_space_id, preprocessor, env_spec, observation_space, action_space, time_batch_size,
                 num_timesteps, eval_mode):
        """
        Subclasses of TaskBase contain all information that should be consistent within a task for everyone
        trying to use it for a baseline. In other words anything that should be kept comparable, should be specified
        here.
        :param action_space_id: An identifier that is consistent between all times we run any tasks that share an
        action space. This is basically how we identify that two tasks are intended to be the same.
        :param preprocessor: A subclass of PreprocessBase that handles the input type of this task.
        :param env_spec: A gym environment name OR a lambda that creates an environment.
        :param observation_space: The observation space that will be passed to the policy,
        not including batch, if applicable, or time_batch_size.
        :param action_space: The action_space the environment of this task uses.
        :param time_batch_size: The number of steps in time that will be concatenated together
        :param num_timesteps: The total number of timesteps this task should run
        :param eval_mode: Whether this environment is being run in eval_mode (i.e. training should not occur)
        should end.
        """
        self.action_space_id = action_space_id
        self.action_space = action_space
        self.time_batch_size = time_batch_size

        # We stack frames in the first dimension, so update the observation to include this.
        old_space = observation_space
        self.observation_space = gym.spaces.Box(
            low=old_space.low.min(),  # .min to turn the array back to a scalar
            high=old_space.high.max(),  # .max to turn the array back to a scalar
            shape=[time_batch_size, *old_space.shape],
            dtype=old_space.dtype,
        )

        # The set of task parameters that the environment runner gets access to.
        self._task_spec = TaskSpec(action_space_id, preprocessor, env_spec, time_batch_size, num_timesteps, eval_mode)

        # A running mean of rewards so the average is less dependent on how many episodes completed in the last update
        self._rewards_to_report = []
        self._rolling_reward_count = 100  # The number OpenAI baselines uses. Represents # rewards to keep between logs

    def _report_log(self, summary_writer, log, run_id, default_timestep):
        type = log["type"]
        tag = f"{log['tag']}/{run_id}"
        value = log["value"]
        timestep = log.get("timestep", None) or default_timestep

        if type == "video":
            summary_writer.add_video(tag, value, global_step=timestep)
        elif type == "scalar":
            summary_writer.add_scalar(tag, value, global_step=timestep)
        elif type == "image":
            summary_writer.add_image(tag, value, global_step=timestep)

        summary_writer.flush()

    def run(self, run_id, policy, summary_writer):
        total_timesteps = 0
        environment_runner = policy.get_environment_runner()
        task_spec = self._task_spec

        while total_timesteps < task_spec.num_timesteps:
            # all_env_data is a list of timestep_datas
            timesteps, all_env_data, rewards_to_report, logs_to_report = environment_runner.collect_data(task_spec)

            if not task_spec.eval_mode:
                policy.train(all_env_data)

            total_timesteps += timesteps

            self._rewards_to_report.extend(rewards_to_report)
            if len(self._rewards_to_report) > 0:
                mean_rewards = np.array(self._rewards_to_report).mean()
                print(f"{total_timesteps}: {mean_rewards}")
                logs_to_report.append({"type": "scalar", "tag": f"reward", "value": mean_rewards,
                                       "timestep": total_timesteps})
            self._rewards_to_report = self._rewards_to_report[-self._rolling_reward_count:]

            for log in logs_to_report:
                if summary_writer is not None:
                    self._report_log(summary_writer, log, run_id, default_timestep=total_timesteps)
                else:
                    print(log)

        environment_runner.cleanup()
