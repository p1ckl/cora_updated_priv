import numpy as np
from continual_rl.experiments.environment_runners.environment_runner_batch import EnvironmentRunnerBatch
from continual_rl.experiments.tasks.task_base import TaskSpec
from tests.common_mocks.mock_policy.mock_policy import MockPolicy
from tests.common_mocks.mock_policy.mock_policy_config import MockPolicyConfig
from tests.common_mocks.mock_policy.mock_timestep_data import MockTimestepData
from tests.common_mocks.mock_preprocessor import MockPreprocessor


class MockEnv(object):
    def __init__(self):
        self.actions_executed = []
        self.reset_count = 0
        self.observation_space = 4
        self.action_space = 4
        self.seed_set = None

    def seed(self, seed):
        self.seed_set = seed

    def reset(self):
        self.reset_count += 1
        return np.array([0, 1, 2]), {"info": "unused"}

    def step(self, action):
        self.actions_executed.append(action)
        observation = np.array([12, 13, 14])
        reward = 1.5
        terminated = action == 4  # Simple way to force the done state we want
        return observation, reward, terminated, False, {"info": "unused"}

    def close(self):
        pass


class TestEnvironmentRunnerBatch(object):

    def test_collect_data_simple_success(self, monkeypatch):
        """
        Setup the simple happy-path for collect_data, and make sure things are being populated correctly.
        Simple: no done=True, no rewards returned, etc.
        """
        # Arrange
        def mock_compute_action(_, observation, task_id, action_space_id, last_timestep_data, eval_mode):
            # Since we're using the Batch runner, it expects a vector
            action = [3] * len(observation)
            timestep_data = MockTimestepData(data_to_store=(observation, task_id, action_space_id, eval_mode))

            if last_timestep_data is None:
                timestep_data.memory = 0
            else:
                timestep_data.memory = last_timestep_data.memory + 1

            return action, timestep_data

        # Mock the policy we're running; action_space and observation_space not used.
        mock_policy = MockPolicy(MockPolicyConfig(), action_spaces=None, observation_space=None)
        monkeypatch.setattr(MockPolicy, "compute_action", mock_compute_action)

        # The object under test
        runner = EnvironmentRunnerBatch(policy=mock_policy, num_parallel_envs=12, timesteps_per_collection=123)

        # Arguments to collect_data
        # Normally should create a new one each time, but doing this for spying
        mock_env = MockEnv()
        mock_env_spec = lambda: mock_env

        # MockEnv is used for determining that parameters are getting generated and passed correctly
        task_spec = TaskSpec(task_id=5, action_space_id=3, preprocessor=MockPreprocessor(), env_spec=mock_env_spec,
                             num_timesteps=9718, eval_mode=1817)

        # Act
        timesteps, collected_data, rewards_reported, _ = runner.collect_data(task_spec)

        # Assert
        # Basic return checks
        assert timesteps == 123 * 12, f"Number of timesteps returned inaccurate. Got {timesteps}."
        assert len(collected_data) == 1, f"Batch env only runs on one process, so return accordingly"
        collected_data = collected_data[0]  # Convenience for the rest of the assertions

        assert len(collected_data) == 123, f"Amount of collected data unexpected. Got {len(collected_data)}."
        assert len(rewards_reported) == 0, "Rewards were reported when none were expected."

        # Check that MockTimestepData is getting properly updated
        assert isinstance(collected_data[0], MockTimestepData), "Unexpected TimestepData returned."
        assert np.all(np.array([entry.reward for entry in collected_data]) == 1.5), \
            "MockTimestepData not correctly populated with reward."
        assert not np.any(np.array([entry.done for entry in collected_data])), \
            "MockTimestepData not correctly populated with done."
        assert collected_data[0].memory == 0, "compute_action not correctly receiving last_timestep_data."
        assert collected_data[1].memory == 1, "compute_action not correctly receiving last_timestep_data."
        assert collected_data[78].memory == 78, "compute_action not correctly receiving last_timestep_data."

        # Check that the observation is being created correctly
        observation_to_policy, received_task_id,  received_action_space_id, observed_eval_mode = collected_data[0].data_to_store
        assert received_task_id == 5, "task_id getting intercepted somehow."
        assert received_action_space_id == 3, "action_space_id getting intercepted somehow."
        assert observation_to_policy.shape[0] == 12, "Envs not being batched correctly"
        assert observed_eval_mode == 1817, "Eval mode not passed correctly"

        # 3 is from how MockEnv is written, which returns observations of length 3
        assert observation_to_policy.shape[1] == 3, "Incorrect obs shape"
        assert mock_env.seed_set is not None, "No seed was set"

        # Use our environment spy to check it's being called correctly
        # All env params are *1 not *12 because the first env is done local to the current process, so this is only
        # one env's worth, even though technically we're returning the same env every time (for spying purposes)
        # It's odd.
        assert mock_env.reset_count == 1, f"Mock env reset an incorrect number of times: {mock_env.reset_count}"
        assert len(mock_env.actions_executed) == 123, "Mock env.step not called a sufficient number of times"
        assert np.all(np.array(mock_env.actions_executed) == 3), "Incorrect action taken"

    def test_collect_data_with_intermediate_dones(self, monkeypatch):
        """
        Setup an environment that gives "done" at some point during the run
        """
        # Arrange
        current_step = 0

        def mock_compute_action(_, observation, task_id, action_space_id, last_timestep_data, eval_mode):
            nonlocal current_step
            action = [4 if current_step == 73 else 3] * len(observation)  # 4 is the "done" action, 3 is arbitrary
            current_step += 1
            timestep_data = MockTimestepData(data_to_store=(observation, task_id, action_space_id, eval_mode))

            if last_timestep_data is None:
                timestep_data.memory = 0
            else:
                timestep_data.memory = last_timestep_data.memory + 1

            return action, timestep_data

        # Mock the policy we're running. action_space and observation_space not used.
        mock_policy = MockPolicy(MockPolicyConfig(), action_spaces=None, observation_space=None)
        monkeypatch.setattr(MockPolicy, "compute_action", mock_compute_action)

        # The object under test
        runner = EnvironmentRunnerBatch(policy=mock_policy, num_parallel_envs=12, timesteps_per_collection=123)

        # Arguments to collect_data
        # Normally should create a new one each time, but doing this for spying
        mock_env = MockEnv()
        mock_env_spec = lambda: mock_env

        # MockEnv is used for determining that parameters are getting generated and passed correctly
        task_spec = TaskSpec(task_id=2, action_space_id=7, preprocessor=MockPreprocessor(), env_spec=mock_env_spec,
                             num_timesteps=9718, eval_mode=1817)

        # Act
        timesteps, collected_data, rewards_reported, _ = runner.collect_data(task_spec)

        # Assert
        # Basic return checks
        assert timesteps == 123 * 12, f"Number of timesteps returned inaccurate. Got {timesteps}."
        assert len(collected_data) == 1, f"Batch env only runs on one process, so return accordingly"
        collected_data = collected_data[0]  # Convenience for the rest of the assertions

        assert len(collected_data) == 123, f"Amount of collected data unexpected. Got {len(collected_data)}."
        assert len(rewards_reported) == 12, "Rewards were not reported when multiple were expected."
        assert np.all(np.array(rewards_reported) == 74 * 1.5), f"Value of reward reported unexpected {rewards_reported}"

        # Check that MockTimestepData is getting properly updated
        assert isinstance(collected_data[0], MockTimestepData), "Unexpected TimestepData returned."
        assert not np.any(np.array([entry.done for entry in collected_data[:73]])), \
            "MockTimestepData not correctly populated with done."
        assert not np.any(np.array([entry.done for entry in collected_data[74:]])), \
            "MockTimestepData not correctly populated with done."
        assert np.all(collected_data[73].done), "MockTimestepData not correctly populated with done."
        assert collected_data[78].memory == 78, "compute_action not correctly receiving last_timestep_data. " \
                                                "(Always populated, even if a done occurred.)"

        # Check that the observation is being created correctly
        observation_to_policy, received_task_id, received_action_space_id, observed_eval_mode = collected_data[0].data_to_store
        assert received_task_id == 2, "task_id getting intercepted somehow."
        assert received_action_space_id == 7, "action_space_id getting intercepted somehow."
        assert observation_to_policy.shape[0] == 12, "Envs not being batched correctly"
        assert observed_eval_mode == 1817, "Eval mode not passed correctly"

        # 3 is from how MockEnv is written, which returns observations of length 3
        assert observation_to_policy.shape[1] == 3, "Incorrect obs shape"

        # Use our environment spy to check it's being called correctly
        # All env params are *1 not *12 because the first env is done local to the current process, so this is only
        # one env's worth, even though technically we're returning the same env every time (for spying purposes)
        # It's odd.
        assert mock_env.reset_count == 2, f"Mock env reset an incorrect number of times: {mock_env.reset_count}"
        assert len(mock_env.actions_executed) == 123, "Mock env.step not called a sufficient number of times"
        assert np.all(np.array(mock_env.actions_executed[:73]) == 3), "Incorrect action taken, first half"
        assert np.all(np.array(mock_env.actions_executed[74:]) == 3), "Incorrect action taken, second half"
        assert np.array(mock_env.actions_executed)[73] == 4, "Incorrect action taken at the 'done' step."

    def test_collect_data_multi_collect_before_done(self, monkeypatch):
        """
        Run two data collections, and make sure the rewards are collected successfully.
        """
        # Arrange
        # Mock methods
        current_step = 0

        def mock_compute_action(_, observation, task_id, action_space_id, last_timestep_data, eval_mode):
            nonlocal current_step
            action = [4 if current_step == 73 else 3] * len(observation)  # 4 is the "done" action, 3 is arbitrary
            current_step += 1
            timestep_data = MockTimestepData(data_to_store=(observation, task_id, action_space_id, eval_mode))

            if last_timestep_data is None:
                timestep_data.memory = 0
            else:
                timestep_data.memory = last_timestep_data.memory + 1

            return action, timestep_data

        # Mock the policy we're running. action_space and observation_space not used.
        mock_policy = MockPolicy(MockPolicyConfig(), action_spaces=None, observation_space=None)
        monkeypatch.setattr(MockPolicy, "compute_action", mock_compute_action)

        # The object under test
        runner = EnvironmentRunnerBatch(policy=mock_policy, num_parallel_envs=12, timesteps_per_collection=50)

        # Arguments to collect_data
        # Normally should create a new one each time, but doing this for spying
        mock_env = MockEnv()
        mock_env_spec = lambda: mock_env

        # MockEnv is used for determining that parameters are getting generated and passed correctly
        task_spec = TaskSpec(task_id=5, action_space_id=6, preprocessor=MockPreprocessor(), env_spec=mock_env_spec,
                             num_timesteps=9718, eval_mode=1817)

        # Act
        timesteps_0, collected_data_0, rewards_reported_0, _ = runner.collect_data(task_spec)
        timesteps_1, collected_data_1, rewards_reported_1, _ = runner.collect_data(task_spec)

        # Assert
        # Basic return checks
        assert timesteps_0 == timesteps_1 == 50 * 12, f"Number of timesteps returned inaccurate. " \
                                                 f"Got {(timesteps_0, timesteps_1)}."
        assert len(collected_data_0) == len(collected_data_1) == 1, f"Batch env only runs on one process, so return accordingly"
        collected_data_0 = collected_data_0[0]  # Convenience for the rest of the assertions
        collected_data_1 = collected_data_1[0]  # Convenience for the rest of the assertions

        assert len(collected_data_0) == len(collected_data_1) == 50, f"Amount of collected data unexpected. " \
                                                                     f"Got {(len(collected_data_0), len(collected_data_1))}."
        assert len(rewards_reported_0) == 0, "Rewards were reported when none were expected."
        assert len(rewards_reported_1) == 12, "Rewards were not reported when multiple were expected."
        assert np.all(np.array(rewards_reported_1) == 74 * 1.5), f"Value of reward reported unexpected {rewards_reported_1}"

        # Check that MockTimestepData is getting properly updated
        assert not np.any(np.array([entry.done for entry in collected_data_0])), \
            "MockTimestepData not correctly populated with done."
        assert not np.any(np.array([entry.done for entry in collected_data_1[:23]])), \
            "MockTimestepData not correctly populated with done."
        assert not np.any(np.array([entry.done for entry in collected_data_1[24:]])), \
            "MockTimestepData not correctly populated with done."
        assert np.all(collected_data_1[23].done), "MockTimestepData not correctly populated with done."
        assert collected_data_1[45].memory == 95, "MockTimestepData not correctly populated with done."

        # Use our environment spy to check it's being called correctly
        # All env params are *1 not *12 because the first env is done local to the current process, so this is only
        # one env's worth, even though technically we're returning the same env every time (for spying purposes)
        # It's odd. But kinda convenient I suppose.
        assert mock_env.reset_count == 2, f"Mock env reset an incorrect number of times: {mock_env.reset_count}"
        assert len(mock_env.actions_executed) == 100, "Mock env.step not called a sufficient number of times"
        assert np.all(np.array(mock_env.actions_executed[:73]) == 3), "Incorrect action taken, first half"
        assert np.all(np.array(mock_env.actions_executed[74:]) == 3), "Incorrect action taken, second half"
        assert np.array(mock_env.actions_executed)[73] == 4, "Incorrect action taken at the 'done' step."

    def test_collect_data_multi_collect_before_done_envs_finish_at_different_times(self, monkeypatch):
        """
        Run two data collections, and make sure the rewards are collected successfully even if not all envs finish together.
        """
        # Arrange
        # Mock methods
        current_step = 0

        def mock_compute_action(_, observation, task_id, action_space_id, last_timestep_data, eval_mode):
            nonlocal current_step
            action = [3] * len(observation)  # 4 is the "done" action, 3 is arbitrary

            # Make a pseudo-random environment finish, but not the others
            if current_step == 73:
                action[8] = 4

            current_step += 1
            return action, MockTimestepData(data_to_store=(observation, task_id, action_space_id, eval_mode))

        # Mock the policy we're running. action_space and observation_space not used.
        mock_policy = MockPolicy(MockPolicyConfig(), action_spaces=None, observation_space=None)
        monkeypatch.setattr(MockPolicy, "compute_action", mock_compute_action)

        # The object under test
        runner = EnvironmentRunnerBatch(policy=mock_policy, num_parallel_envs=12, timesteps_per_collection=50)

        # Arguments to collect_data
        # Normally should create a new one each time, but doing this for spying
        mock_env = MockEnv()
        mock_env_spec = lambda: mock_env

        # MockEnv is used for determining that parameters are getting generated and passed correctly
        task_spec = TaskSpec(task_id=5, action_space_id=6, preprocessor=MockPreprocessor(), env_spec=mock_env_spec,
                             num_timesteps=9718, eval_mode=1817)

        # Act
        timesteps_0, collected_data_0, rewards_reported_0, _ = runner.collect_data(task_spec)
        timesteps_1, collected_data_1, rewards_reported_1, _ = runner.collect_data(task_spec)

        # Assert
        # Basic return checks
        assert timesteps_0 == timesteps_1 == 50 * 12, f"Number of timesteps returned inaccurate. " \
                                                      f"Got {(timesteps_0, timesteps_1)}."
        assert len(collected_data_0) == len(collected_data_1) == 1, f"Batch env only runs on one process, so return accordingly"
        collected_data_0 = collected_data_0[0]  # Convenience for the rest of the assertions
        collected_data_1 = collected_data_1[0]  # Convenience for the rest of the assertions

        assert len(collected_data_0) == len(collected_data_1) == 50, f"Amount of collected data unexpected. " \
                                                                     f"Got {(len(collected_data_0), len(collected_data_1))}."
        assert len(rewards_reported_0) == 0, "Rewards were reported when none were expected."
        assert len(rewards_reported_1) == 1, "Rewards were not reported when one was expected."
        assert rewards_reported_1[0] == 74 * 1.5, f"Value of reward reported unexpected {rewards_reported_1}"

        # Check that MockTimestepData is getting properly updated
        assert not np.any(np.array([entry.done for entry in collected_data_0])), \
            "MockTimestepData not correctly populated with done."
        assert not np.any(np.array([entry.done for entry in collected_data_1[:23]])), \
            "MockTimestepData not correctly populated with done."
        assert not np.any(np.array([entry.done for entry in collected_data_1[24:]])), \
            "MockTimestepData not correctly populated with done."
        assert not np.any(collected_data_1[23].done[:8]), "MockTimestepData not correctly populated with done."
        assert not np.any(collected_data_1[23].done[9:]), "MockTimestepData not correctly populated with done."
        assert collected_data_1[23].done[8], "MockTimestepData not correctly populated with done."

        # Use our environment spy to check it's being called correctly
        # All env params are *1 not *12 because the first env is done local to the current process, so this is only
        # one env's worth, even though technically we're returning the same env every time (for spying purposes)
        # It's odd. But kinda convenient I suppose.
        assert mock_env.reset_count == 1, f"Mock env reset an incorrect number of times: {mock_env.reset_count}"
        assert len(mock_env.actions_executed) == 100, "Mock env.step not called a sufficient number of times"
        assert np.all(np.array(mock_env.actions_executed) == 3), "Incorrect action taken by the first env"
