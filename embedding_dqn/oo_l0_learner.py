
import tensorflow as tf
import numpy as np
import tf_helpers as th
import rmax_learner
from oo_replay_memory import MMCPathTracker
from oo_replay_memory import ReplayMemory


def construct_root_network(input, frame_history):
    input = tf.image.convert_image_dtype(input, tf.float32)
    with tf.variable_scope('c1'):
        c1 = th.down_convolution(input, 8, 4, frame_history, 32, tf.nn.relu)
    with tf.variable_scope('c2'):
        c2 = th.down_convolution(c1, 4, 2, 32, 64, tf.nn.relu)
    with tf.variable_scope('c3'):
        c3 = th.down_convolution(c2, 3, 1, 64, 64, tf.nn.relu)
        N = np.prod([x.value for x in c3.get_shape()[1:]])
        c3 = tf.reshape(c3, [-1, N])
    return c3


def construct_heads_network(input, num_actions, num_abstract_states):
    num_heads = num_abstract_states * num_abstract_states
    with tf.variable_scope('fc1'):
        fc1 = th.fully_connected(input, 512, tf.nn.relu)
    with tf.variable_scope('fc2'):
        q_values = th.fully_connected_multi_shared_bias(fc1, num_actions, num_heads, lambda x: x)
        q_values = tf.reshape(q_values, [-1, num_heads, num_actions])
    return q_values


def construct_dqn_with_embedding(input, abs_state1, abs_state2, frame_history, num_actions):
    embedding, weights = construct_embedding_network(abs_state1, abs_state2, 50, 50,
                                                     512 * num_actions + 1)  # plus 1 for shared bias
    w = tf.reshape(weights[:, 0:512 * num_actions], [-1, 512, num_actions])
    b = tf.reshape(weights[:, 512 * num_actions:512 * num_actions + 1], [-1, 1])
    input = tf.image.convert_image_dtype(input, tf.float32)
    with tf.variable_scope('c1'):
        c1 = th.down_convolution(input, 8, 4, frame_history, 32, tf.nn.relu)
    with tf.variable_scope('c2'):
        c2 = th.down_convolution(c1, 4, 2, 32, 64, tf.nn.relu)
    with tf.variable_scope('c3'):
        c3 = th.down_convolution(c2, 3, 1, 64, 64, tf.nn.relu)
        N = np.prod([x.value for x in c3.get_shape()[1:]])
        c3 = tf.reshape(c3, [-1, N])
    with tf.variable_scope('fc1'):
        fc1 = th.fully_connected(c3, 512, tf.nn.relu)
    with tf.variable_scope('fc2'):
        q_values = tf.reshape(tf.matmul(tf.reshape(fc1, [-1, 1, 512]), w), [-1, num_actions]) + b
    return q_values


def construct_dqn_with_embedding_2_layer(input, abs_state1, abs_state2, frame_history, num_actions):
    embedding, weights = construct_embedding_network(abs_state1, abs_state2, 200, 200,
                                                     512 * num_actions + 1)  # plus 1 for shared bias
    w = tf.reshape(weights[:, 0:512 * num_actions], [-1, 512, num_actions])
    b = tf.reshape(weights[:, 512 * num_actions:512 * num_actions + 1], [-1, 1])
    input = tf.image.convert_image_dtype(input, tf.float32)
    with tf.variable_scope('c1'):
        c1 = th.down_convolution(input, 8, 4, frame_history, 32, tf.nn.relu)
    with tf.variable_scope('c2'):
        c2 = th.down_convolution(c1, 4, 2, 32, 64, tf.nn.relu)
    with tf.variable_scope('c3'):
        c3 = th.down_convolution(c2, 3, 1, 64, 64, tf.nn.relu)
        N = np.prod([x.value for x in c3.get_shape()[1:]])
        c3 = tf.reshape(c3, [-1, N])
    with tf.variable_scope('fc1'):
        fc1 = th.fully_connected(c3, 512, tf.nn.relu)
    with tf.variable_scope('fc2'):
        q_values = tf.reshape(tf.matmul(tf.reshape(fc1, [-1, 1, 512]), w), [-1, num_actions]) + b
    return q_values


def legacy_concat(dim=None, data=None):
    if dim == None or data == None:
        raise Exception('need to specify both concat dimension and data')
    if tf.__version__ == '0.12.1':
        return tf.concat(dim, data)
    else:
        return tf.concat(data, dim)


def construct_dqn_with_subgoal_embedding(input, abs_state1, abs_state2, frame_history, num_actions):
    input = tf.image.convert_image_dtype(input, tf.float32)
    with tf.variable_scope('a1'):
        a1 = th.fully_connected(legacy_concat(data=[abs_state1, abs_state2], dim=1), 50, tf.nn.relu)
    with tf.variable_scope('c1'):
        c1 = th.down_convolution(input, 8, 4, frame_history, 32, tf.nn.relu)
    with tf.variable_scope('c2'):
        c2 = th.down_convolution(c1, 4, 2, 32, 64, tf.nn.relu)
    with tf.variable_scope('c3'):
        c3 = th.down_convolution(c2, 3, 1, 64, 64, tf.nn.relu)
        N = np.prod([x.value for x in c3.get_shape()[1:]])
        c3 = tf.reshape(c3, [-1, N])
        ac3 = legacy_concat(dim=1, data=[a1, c3])
    with tf.variable_scope('fc1'):
        fc1 = th.fully_connected(ac3, 512, tf.nn.relu)
    with tf.variable_scope('fc2'):
        q_values = th.fully_connected_shared_bias(fc1, num_actions, lambda x: x)
    return q_values


def construct_embedding_network(abs_state1, abs_state2, hidden_size, embedding_size, weight_size):
    def shared_abs(inp, neurons):
        with tf.variable_scope('fc1'):
            fc1 = th.fully_connected(inp, neurons, tf.nn.relu)
        with tf.variable_scope('fc2'):
            A = th.fully_connected(fc1, neurons, tf.nn.relu)
        return A

    with tf.variable_scope('A'):
        A1 = shared_abs(abs_state1, hidden_size)
    with tf.variable_scope('A', reuse=True):
        A2 = shared_abs(abs_state2, hidden_size)
    with tf.variable_scope('pre_embedding'):
        pre_embedding = th.fully_connected(tf.concat([A1, A2], 1), hidden_size * 2, tf.nn.relu)
    with tf.variable_scope('embedding'):
        embedding = th.fully_connected(pre_embedding, embedding_size, lambda x: x)
    with tf.variable_scope('pre_weights'):
        pre_weights = th.fully_connected(embedding, embedding_size, tf.nn.relu)
    with tf.variable_scope('weights'):
        weights = th.fully_connected(pre_weights, weight_size, lambda x: x)
    return embedding, weights


def construct_q_network_weights(input, dqn_numbers, dqn_max_number, frame_history, num_actions):
    input = tf.image.convert_image_dtype(input, tf.float32)
    with tf.variable_scope('c1'):
        c1 = th.down_convolution_weights(input, dqn_numbers, dqn_max_number, 8, 4, frame_history, 32, tf.nn.relu)
    with tf.variable_scope('c2'):
        c2 = th.down_convolution_weights(c1, dqn_numbers, dqn_max_number, 4, 2, 32, 64, tf.nn.relu)
    with tf.variable_scope('c3'):
        c3 = th.down_convolution_weights(c2, dqn_numbers, dqn_max_number, 3, 1, 64, 64, tf.nn.relu)
        N = np.prod([x.value for x in c3.get_shape()[1:]])
        # N = tf.reduce_prod(tf.shape(c3)[1:4])
        # N = []
        c3 = tf.reshape(c3, [-1, N])
    with tf.variable_scope('fc1'):
        fc1 = th.fully_connected_weights(c3, dqn_numbers, dqn_max_number, 512, tf.nn.relu)
    with tf.variable_scope('fc2'):
        q_values = th.fully_connected_weights(fc1, dqn_numbers, dqn_max_number, num_actions, lambda x: x)
    return q_values

def construct_q_network_weights_only_final(input, dqn_numbers, dqn_max_number, frame_history, num_actions):
    input = tf.image.convert_image_dtype(input, tf.float32)
    with tf.variable_scope('c1'):
        c1 = th.down_convolution(input, 8, 4, frame_history, 32, tf.nn.relu)
    with tf.variable_scope('c2'):
        c2 = th.down_convolution(c1, 4, 2, 32, 64, tf.nn.relu)
    with tf.variable_scope('c3'):
        c3 = th.down_convolution(c2, 3, 1, 64, 64, tf.nn.relu)
        N = np.prod([x.value for x in c3.get_shape()[1:]])
        # N = tf.reduce_prod(tf.shape(c3)[1:4])
        # N = []
        c3 = tf.reshape(c3, [-1, N])
    with tf.variable_scope('fc1'):
        fc1 = th.fully_connected(c3, 512, tf.nn.relu)
    with tf.variable_scope('fc2'):
        q_values = th.fully_connected_weights_2(fc1, dqn_numbers, dqn_max_number, num_actions, lambda x: x)
    return q_values


def leaky_relu(x, alpha=0.001):
    return tf.maximum(x, alpha * x)


def construct_small_network_weights(input, dqn_numbers, dqn_max_number, frame_history, num_actions):
    input = tf.image.convert_image_dtype(input, tf.float32)
    with tf.variable_scope('c1'):
        c1 = th.down_convolution_weights(input, dqn_numbers, dqn_max_number, 5, 5, frame_history, 16, leaky_relu)
    with tf.variable_scope('c2'):
        c2 = th.down_convolution_weights(c1, dqn_numbers, dqn_max_number, 5, 5, 16, 4, leaky_relu)
        N = np.prod([x.value for x in c2.get_shape()[1:]])
        c2 = tf.reshape(c2, [-1, N])
    with tf.variable_scope('fc1'):
        fc1 = th.fully_connected_weights(c2, dqn_numbers, dqn_max_number, 15, leaky_relu)
    with tf.variable_scope('fc2'):
        q_values = th.fully_connected_weights(fc1, dqn_numbers, dqn_max_number, num_actions, lambda x: x)
    return q_values


def construct_meta_dqn_network(input, abs_state1, abs_state2, frame_history, num_actions):
    input = tf.image.convert_image_dtype(input, tf.float32)
    meta_input = tf.concat([abs_state1, abs_state2], axis=1)
    with tf.variable_scope('c1'):
        c1 = th.down_convolution_meta(input, meta_input, 5, 5, 16, th.selu, meta_weight_size=500)
    with tf.variable_scope('c2'):
        c2 = th.down_convolution_meta(c1, meta_input, 5, 5, 4, th.selu, meta_weight_size=500)
        N = np.prod([x.value for x in c2.get_shape()[1:]])
        c2 = tf.reshape(c2, [-1, N])
    with tf.variable_scope('fc1'):
        fc1 = th.fully_connected_meta(c2, meta_input, 15, th.selu, meta_weight_size=500)
    with tf.variable_scope('fc2'):
        q_values = th.fully_connected_meta(fc1, meta_input, num_actions, lambda x: x, meta_weight_size=500)
    return q_values


class MultiHeadedDQLearner():
    def __init__(self, abs_size, num_actions, num_abstract_states, gamma=0.99, learning_rate=0.00025,
                 replay_start_size=500,
                 epsilon_start=1.0, epsilon_end=0.01, epsilon_steps=100000,
                 update_freq=4, target_copy_freq=30000, replay_memory_size=1000000,
                 frame_history=4, batch_size=32, error_clip=1, restore_network_file=None, double=True,
                 use_mmc=False, max_mmc_path_length=1000, mmc_beta=0.0, max_dqn_number=300, rmax_learner=None,
                 encoding_func=None, bonus_beta=0.05):
        self.rmax_learner = rmax_learner
        config = tf.ConfigProto()
        config.gpu_options.allow_growth = True
        config.allow_soft_placement = True
        self.sess = tf.Session(config=config)
        self.inp_actions = tf.placeholder(tf.float32, [None, num_actions])
        self.max_mmc_path_length = max_mmc_path_length
        self.mmc_beta = mmc_beta
        inp_shape = [None, 84, 84, frame_history]
        inp_dtype = 'uint8'
        assert type(inp_dtype) is str
        self.inp_frames = tf.placeholder(inp_dtype, inp_shape)
        self.inp_sp_frames = tf.placeholder(inp_dtype, inp_shape)
        self.inp_terminated = tf.placeholder(tf.bool, [None])
        self.inp_reward = tf.placeholder(tf.float32, [None])
        self.inp_mmc_reward = tf.placeholder(tf.float32, [None])
        self.inp_mask = tf.placeholder(inp_dtype, [None, frame_history])
        self.inp_sp_mask = tf.placeholder(inp_dtype, [None, frame_history])
        self.inp_dqn_numbers = tf.placeholder(tf.int32, [None])
        # self.inp_q_choices = tf.placeholder(tf.int32, [None])

        self.abs_neighbors = dict()
        self.gamma = gamma
        self.max_dqn_number = max_dqn_number
        # q_constructor = lambda inp: construct_q_network_weights(inp, self.inp_dqn_numbers, max_dqn_number, frame_history, num_actions)
        #q_constructor = lambda inp: construct_small_network_weights(inp, self.inp_dqn_numbers, max_dqn_number,
        #                                                            frame_history, num_actions)
        #q_constructor = lambda inp: construct_dqn_with_embedding_2_layer(inp, self.inp_abs_state_init, self.inp_abs_state_goal, frame_history, num_actions)
        q_constructor = lambda inp: construct_q_network_weights_only_final(inp, self.inp_dqn_numbers, max_dqn_number,
                                                                    frame_history, num_actions)
        # q_constructor = lambda inp: construct_dqn_with_subgoal_embedding(inp, self.inp_abs_state_init, self.inp_abs_state_goal, frame_history, num_actions)
        # q_constructor = lambda inp: construct_meta_dqn_network(inp, self.inp_abs_state_init, self.inp_abs_state_goal, frame_history, num_actions)
        with tf.variable_scope('online'):
            mask_shape = [-1, 1, 1, frame_history]
            mask = tf.reshape(self.inp_mask, mask_shape)
            masked_input = self.inp_frames * mask
            self.q_online = q_constructor(masked_input)
        with tf.variable_scope('target'):
            mask_shape = [-1, 1, 1, frame_history]
            sp_mask = tf.reshape(self.inp_sp_mask, mask_shape)
            masked_sp_input = self.inp_sp_frames * sp_mask
            self.q_target = q_constructor(masked_sp_input)

        if double:
            with tf.variable_scope('online', reuse=True):
                self.q_online_prime = q_constructor(masked_sp_input)
                print self.q_online_prime
            self.maxQ = tf.gather_nd(self.q_target, tf.transpose(
                [tf.range(0, batch_size, dtype=tf.int32), tf.cast(tf.argmax(self.q_online_prime, axis=1), tf.int32)],
                [1, 0]))
        else:
            self.maxQ = tf.reduce_max(self.q_target, axis=1)

        self.r = self.inp_reward
        use_backup = tf.cast(tf.logical_not(self.inp_terminated), dtype=tf.float32)
        self.y = self.r + use_backup * gamma * self.maxQ

        self.delta_dqn = tf.reduce_sum(self.inp_actions * self.q_online, axis=1) - self.y
        self.error_dqn = tf.where(tf.abs(self.delta_dqn) < error_clip, 0.5 * tf.square(self.delta_dqn),
                                  error_clip * tf.abs(self.delta_dqn))
        if use_mmc:
            self.delta_mmc = tf.reduce_sum(self.inp_actions * self.q_online, axis=1) - self.inp_mmc_reward
            self.error_mmc = tf.where(tf.abs(self.delta_mmc) < error_clip, 0.5 * tf.square(self.delta_mmc),
                                      error_clip * tf.abs(self.delta_mmc))
            # self.delta = (1. - self.mmc_beta) * self.delta_dqn + self.mmc_beta * self.delta_mmc
            self.loss = (1. - self.mmc_beta) * tf.reduce_sum(self.error_dqn) + self.mmc_beta * tf.reduce_sum(
                self.error_mmc)
        else:
            self.loss = tf.reduce_sum(self.error_dqn)
        self.g = tf.gradients(self.loss, self.q_online)
        optimizer = tf.train.RMSPropOptimizer(learning_rate=learning_rate, decay=0.95, centered=True, epsilon=0.01)
        self.pre_gvs = optimizer.compute_gradients(self.loss, var_list=th.get_vars('online'))
        self.pre_gvs = [(tf.where(tf.is_nan(grad), tf.zeros_like(grad), grad), var) for grad, var in self.pre_gvs]
        self.post_gvs = [(tf.clip_by_value(grad, -10., 10.), var) for grad, var in self.pre_gvs]
        self.train_op = optimizer.apply_gradients(self.post_gvs)
        self.copy_op = th.make_copy_op('online', 'target')
        self.saver = tf.train.Saver(var_list=th.get_vars('online'))

        self.use_mmc = use_mmc
        self.replay_buffer = ReplayMemory((84, 84), abs_size, 'uint8', replay_memory_size, frame_history)
        if self.use_mmc:
            self.mmc_tracker = MMCPathTracker(self.replay_buffer, self.max_mmc_path_length, self.gamma)
        self.frame_history = frame_history
        self.replay_start_size = replay_start_size
        self.epsilon = [epsilon_start] * num_abstract_states * num_abstract_states
        self.epsilon = dict()
        self.global_epsilon = epsilon_start
        self.epsilon_min = epsilon_end
        self.epsilon_steps = epsilon_steps
        self.epsilon_delta = (epsilon_start - self.epsilon_min) / self.epsilon_steps
        self.update_freq = update_freq
        self.target_copy_freq = target_copy_freq
        self.action_ticker = 1

        self.num_actions = num_actions
        self.batch_size = batch_size

        self.check_op = tf.add_check_numerics_ops()
        self.sess.run(tf.initialize_all_variables())

        if restore_network_file is not None:
            self.saver.restore(self.sess, restore_network_file)
            print 'Restored network from file'
        self.sess.run(self.copy_op)

        self.encoding_func = encoding_func
        self.bonus_beta = bonus_beta
        self.reward_mult = 1

        ####################
        ## Keeping track of progress of actions

        self.samples_per_option = 50
        self.state_samples_for_option = dict()
        self.option_action_ticker = dict()
        self.progress_sample_frequency = 1000

        ####################

    def update_q_values(self):
        S1, DQNNumbers, A, R, MMC_R, S2, T, M1, M2 = self.replay_buffer.sample(self.batch_size)
        Aonehot = np.zeros((self.batch_size, self.num_actions), dtype=np.float32)
        Aonehot[range(len(A)), A] = 1

        [_, loss, q_online, maxQ, q_target, r, y, delta_dqn, g, pre_gvs, post_gvs] = self.sess.run(
            [self.train_op, self.loss, self.q_online, self.maxQ, self.q_target, self.r, self.y, self.delta_dqn,
             self.g, self.pre_gvs, self.post_gvs],
            feed_dict={self.inp_frames: S1, self.inp_actions: Aonehot,
                       self.inp_sp_frames: S2, self.inp_reward: R, self.inp_mmc_reward: MMC_R,
                       self.inp_terminated: T, self.inp_mask: M1, self.inp_sp_mask: M2,
                       self.inp_dqn_numbers: DQNNumbers})
        return loss

    def run_learning_episode(self, environment, initial_l1_state, goal_l1_state, dqn_number, abs_func, epsilon, max_episode_steps=100000, cts=None):
        episode_steps = 0
        total_reward = 0
        episode_finished = False
        new_l1_state = initial_l1_state
        dqn_tuple = (initial_l1_state, goal_l1_state)
        if dqn_tuple not in self.epsilon:
            self.epsilon[dqn_tuple] = 1.0

        for steps in range(max_episode_steps):
            if environment.is_current_state_terminal():
                break

            state = environment.get_current_state()

            if np.random.uniform(0, 1) < epsilon:
                action = np.random.choice(environment.get_actions_for_state(state))
                # action = self.get_safe_explore_action(state, environment)
            else:
                action = self.get_action(state, dqn_number)

            if self.replay_buffer.size() > self.replay_start_size:
                self.global_epsilon = max(self.epsilon_min, self.global_epsilon - self.epsilon_delta)
                self.epsilon[dqn_tuple] = max(self.epsilon_min, self.epsilon[dqn_tuple] - self.epsilon_delta)


            state, action, env_reward, next_state, is_terminal = environment.perform_action(action)
            total_reward += env_reward

            new_l1_state = abs_func(next_state)
            # if initial_l1_state != new_l1_state:
            #     self.abs_neighbors[key_init].add(tuple(new_l1_state.get_vector()))

            if initial_l1_state != new_l1_state or is_terminal:
                reward = 1 if new_l1_state == goal_l1_state else 0
                episode_finished = True
            else:
                reward = 0

            if cts is None:
                R_plus = 0
            else:
                enc_s = self.encoding_func(environment)
                n_hat = cts.psuedo_count_for_image(enc_s)
                R_plus = (1 - (episode_finished or is_terminal)) * (self.bonus_beta * np.power(n_hat + 0.01, -0.5))

            R_plus = (self.reward_mult * np.sign(reward)) + R_plus

            if dqn_number != -1:
                if self.use_mmc:
                    sars = (state[-1], dqn_number, action, R_plus, next_state[-1],
                            is_terminal or episode_finished)
                    self.mmc_tracker.append(*sars)
                    if is_terminal or episode_finished:
                        self.mmc_tracker.flush()
                else:
                    sars = (state[-1], dqn_number, action, R_plus, 0, next_state[-1],
                            is_terminal or episode_finished)
                    self.replay_buffer.append(*sars)

            if (self.replay_buffer.size() > self.replay_start_size) and (self.action_ticker % self.update_freq == 0):
                loss = self.update_q_values()
            if (self.action_ticker - self.replay_start_size) % self.target_copy_freq == 0:
                self.sess.run(self.copy_op)
            self.action_ticker += 1
            episode_steps += 1

            if episode_finished:
                break

        return episode_steps, total_reward, new_l1_state

    def get_action(self, state, dqn_number):
        state_input = np.transpose(state, [1, 2, 0])

        [q_values] = self.sess.run([self.q_online],
                                   feed_dict={self.inp_frames: [state_input],
                                              self.inp_mask: np.ones((1, self.frame_history), dtype=np.float32),
                                              self.inp_dqn_numbers: [dqn_number]})
        return np.argmax(q_values[0])

    def get_safe_explore_action(self, state, environment):
        all_actions = environment.get_actions_for_state(state)
        safe_actions = []
        for a in all_actions:
            if environment.is_action_safe(a):
                safe_actions.append(a)

        return np.random.choice(safe_actions)

    def save_network(self, file_name):
        self.saver.save(self.sess, file_name)