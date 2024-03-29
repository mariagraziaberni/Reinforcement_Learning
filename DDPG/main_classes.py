import torch 
import torch.nn as nn 
import torch.nn.functional as F 
import torch.autograd 
import torch.optim as optim 

import numpy as np 
import gym 
from collections import deque 
import random
import os

class OUNoise(object):
    def __init__(self, action_space, mu=0.0, theta=0.15, max_sigma=0.3, min_sigma=0.3, decay_period=100000):
        self.mu = mu
        self.theta = theta
        self.sigma = max_sigma
        self.max_sigma = max_sigma
        self.min_sigma = min_sigma
        self.decay_period = decay_period
        self.action_dim = action_space.shape[0]
        self.low = action_space.low
        self.high = action_space.high
        self.reset()
        
    def reset(self):
        self.state = np.ones(self.action_dim) * self.mu
        
    def evolve_state(self):
        x  = self.state
        dx = self.theta * (self.mu - x) + self.sigma * np.random.randn(self.action_dim)
        self.state = x + dx
        return self.state
    
    def get_action(self, action, t=0):
    
        ou_state = self.evolve_state()
        self.sigma = self.max_sigma - (self.max_sigma - self.min_sigma) * min(1.0, t / self.decay_period)

        return np.clip(action + ou_state, self.low, self.high)
        
        
        
class NormalizedEnv(gym.ActionWrapper):
    """ Wrap action """

    def action(self, action):
        act_k = (self.action_space.high - self.action_space.low)/ 2.
        act_b = (self.action_space.high + self.action_space.low)/ 2.
        return act_k * action + act_b

    def reverse_action(self, action):
        act_k_inv = 2./(self.action_space.high - self.action_space.low)
        act_b = (self.action_space.high + self.action_space.low)/ 2.
        return act_k_inv * (action - act_b)
        
        
        
class Replay_Memory: 
    
    def __init__(self, max_size): 
        
        self.max_size = max_size 
        
        self.buffer = deque(maxlen = max_size)
        
    def push(self, state, action, reward, next_state, done): 
        
        experience = (state, action, np.array([reward]), next_state, done)
        
        self.buffer.append(experience)
        
    def sample(self, batch_size):
        
        state_batch = []
        
        action_batch = [] 
        
        reward_batch = [] 
        
        next_state_batch = [] 
        
        done_batch = [] 
        
        batch = random.sample(self.buffer, batch_size)
        
        for experience in batch: 
            
            state, action, reward, next_state, done = experience 
            
            state_batch.append(state)
            
            action_batch.append(action) 
            
            reward_batch.append(reward) 
            
            next_state_batch.append(next_state)
            
            done_batch.append(not done)
            
        return state_batch, action_batch, reward_batch, next_state_batch, done_batch 
    
    def __len__(self): 
        
        return len(self.buffer)
        
        


class Critic(nn.Module): 
    
    def __init__(self, input_dim, fc1_dim, fc2_dim, n_actions, name=None, chkpt="model"): 
        
        super(Critic, self).__init__() 
        
        self.input_dim = input_dim 
        
        self.fc1_dim = fc1_dim 
        
        self.fc2_dim = fc2_dim 
        
        self.n_actions = n_actions 
        
        if name is not None:
        
            if not os.path.exists(chkpt): 
            
                os.makedirs(chkpt)
                
            self.filename = os.path.join(chkpt, name +'_ddpg')
        
        self.fc1 = nn.Linear(*self.input_dim, self.fc1_dim)
        
        self.bn1 = nn.LayerNorm(self.fc1_dim)
        
        self.fc2 = nn.Linear(self.fc1_dim, self.fc2_dim)
        
        self.bn2 = nn.LayerNorm(self.fc2_dim)
        
        self.action_value = nn.Linear(self.n_actions,fc2_dim)
        
        self.q = nn.Linear(self.fc2_dim,1)
        
    def forward(self, state, action): 
        
        state_value = self.fc1(state)
        
        state_value = self.bn1(state_value)
        
        state_value = F.relu(state_value)
        
        state_value = self.fc2(state_value) 
        
        state_value = self.bn2(state_value) 
        
        action_value = F.relu(self.action_value(action))
        
        state_action_value = F.relu(torch.add(state_value,action_value))  
        
        state_action_value = self.q(state_action_value)
        
        return state_action_value 
    
    def init_weights(self): 
        
        f1 = 1 / np.sqrt(self.fc1.weight.data.size()[0])
        
        f2 = 1 / np.sqrt(self.fc2.weight.data.size()[0])
        
        f3 = 0.003
        
        torch.nn.init.uniform_(self.fc1.weight.data, -f1, f1)
        
        torch.nn.init.uniform_(self.fc1.bias.data, -f1, f1)
        
        torch.nn.init.uniform_(self.fc2.weight.data, -f2, f2)

        torch.nn.init.uniform_(self.fc2.bias.data, -f2, f2)
        
        torch.nn.init.uniform_(self.q.weight.data, -f3, f3)
        
        torch.nn.init.uniform_(self.q.bias.data, -f3, f3)
        
        
    def save_checkpoint(self):
       
        torch.save(self.state_dict(), self.filename)
        print("saving")

    def load_checkpoint(self):
        
        self.load_state_dict(torch.load(self.filename))
        
        



class Actor(nn.Module):
    
    def __init__(self, input_dim, fc1_dim, fc2_dim, n_actions, name=None, chkpt="model"): 
        
        super(Actor, self).__init__()
        
        self.input_dim = input_dim 
        
        self.fc1_dim = fc1_dim 
        
        self.fc2_dim = fc2_dim 
        
        self.n_actions = n_actions 
        
        if name is not None:
        
            if not os.path.exists(chkpt): 
            
                os.makedirs(chkpt)
                
            self.filename = os.path.join(chkpt, name +'_ddpg')
            
        self.fc1 = nn.Linear(*self.input_dim, self.fc1_dim)
        
        self.bn1 = nn.LayerNorm(self.fc1_dim)
        
        self.fc2 = nn.Linear(self.fc1_dim, self.fc2_dim)
        
        self.bn2 = nn.LayerNorm(self.fc2_dim)
        
        self.mu = nn.Linear(self.fc2_dim, self.n_actions)
        
    def forward(self,state):
        
        x = self.fc1(state)
        
        x = self.bn1(x)
        
        x = F.relu(x)
        
        x = self.fc2(x)
        
        x = self.bn2(x)
        
        x = F.relu(x)
        
        x = torch.tanh(self.mu(x))
        
        return x
    
    def init_weights(self): 
        
        f1 = 1 / np.sqrt(self.fc1.weight.data.size()[0])
        
        f2 = 1 / np.sqrt(self.fc2.weight.data.size()[0])
        
        f3 = 0.003
        
        torch.nn.init.uniform_(self.fc1.weight.data, -f1, f1)
        
        torch.nn.init.uniform_(self.fc1.bias.data, -f1, f1)
        
        torch.nn.init.uniform_(self.fc2.weight.data, -f2, f2)

        torch.nn.init.uniform_(self.fc2.bias.data, -f2, f2)
        
        torch.nn.init.uniform_(self.mu.weight.data, -f3, f3)
        
        torch.nn.init.uniform_(self.mu.bias.data, -f3, f3)
        
    
    def save_checkpoint(self):
        
        torch.save(self.state_dict(), self.filename)
        print("saving")

    def load_checkpoint(self):
    
        self.load_state_dict(torch.load(self.filename))
        
        
        
        
class DDPGagent: 
    
    def __init__(self, env, layer1_size, layer2_size,replay_min=100,replay_size=1000000,critic_lr=0.00015, actor_lr=0.000015, tau =0.001, gamma=0.99,loss =nn.MSELoss(), batch_size=64, name_critic = None, name_actor=None, device = "cpu" ,directory = "models"):
        
        self.env = env 
                       
        
        self.input_dim = env.observation_space.shape 
        
        self.n_actions = env.action_space.shape[0]
        
        self.tau = tau 
        
        self.device = device
        
        self.gamma = gamma 
        
        self.batch_size = batch_size 
        
        self.name_critic = name_critic
                                      
        
        self.memory= Replay_Memory(replay_size)
        
        self.replay_min = replay_min
        
        self.name_actor = name_actor 
        
        self.critic = Critic(self.input_dim, layer1_size, layer2_size, self.n_actions, name = name_critic,chkpt=directory).to(device)
        
        name_target_critic = None
        
        if name_critic is not None: 
            
            name_target_critic = name_critic + "_target"
                
        self.target_critic = Critic(self.input_dim, layer1_size, layer2_size, self.n_actions, name = name_target_critic,chkpt=directory).to(device)
        
        self.actor = Actor(self.input_dim, layer1_size, layer2_size, self.n_actions, name = name_actor,chkpt=directory).to(device)
        
        name_target_actor = None 
        
        if name_actor is not None: 
            
            name_target_actor = name_actor + "_target"
            
        self.target_actor = Actor(self.input_dim, layer1_size, layer2_size, self.n_actions, name = name_target_actor,chkpt=directory).to(device)
        
        self.critic.init_weights()
        
        self.actor.init_weights()
        
        self.update_target_weights()
        
        self.critic_criterion = loss 
        
        self.actor_criterion = loss  
        
        self.critic_optimizer = torch.optim.Adam(self.critic.parameters(),lr=critic_lr,weight_decay=0.01)
        
        self.actor_optimizer = torch.optim.Adam(self.actor.parameters(),lr=actor_lr)
    
    def update_critic_optimizer(self, learning_rate): 
        
        self.critic_optimizer = torch.optim.Adam(self.critic.parameters(),lr=learning_rate)
        
    def update_actor_optimizer(self, learning_rate): 
        
        self.actor_optimizer = torch.optim.Adam(self.actor.parameters(),lr=learning_rate)
        
        
    def update_replay_memory(self,state, action, reward, next_state, done): 
        
        self.memory.push(state, action, reward, next_state, done)    
        
        
        
    def update_target_weights(self,tau=1): 
        
        for target_param, param in zip(self.target_critic.parameters(),self.critic.parameters()): 
            
            target_param.data.copy_(param.data * self.tau + target_param.data *(1.0 - tau))
            
        for target_param, param in zip(self.target_actor.parameters(),self.actor.parameters()): 
            
            target_param.data.copy_(param.data * self.tau + target_param.data *(1.0 - tau))
            
            
    def get_action(self, observation): 
        
        self.actor.eval()  #because I have batch norm 
        
        observation = torch.tensor(observation, dtype= torch.float).to(self.device)
     
        actor_action = self.actor(observation)
        
        action = actor_action.cpu().detach().numpy()  
        
        return action 
    
    
    def train(self): 
        
        if len(self.memory) <  self.replay_min:
            
            return 
        
        states, actions, rewards, next_states, not_done = self.memory.sample(self.batch_size)
        
        states = torch.tensor(np.array(states), dtype = torch.float).to(self.device)
        
        actions = torch.tensor(np.array(actions), dtype = torch.float).to(self.device)
        
        rewards = torch.tensor(np.array(rewards), dtype = torch.float).to(self.device)
        
        next_states = torch.tensor(np.array(next_states), dtype = torch.float).to(self.device)
        
        not_done = torch.tensor(np.array(not_done)).unsqueeze(1).to(self.device)
        
        self.actor.eval() 
        
        self.critic.eval() 
        
        self.target_actor.eval() 
        
        self.target_critic.eval() 
        
        target_actions = self.target_actor.forward(next_states)
        
        target_critic_value = self.target_critic(next_states, target_actions) 
        
    
        
        targets = rewards + self.gamma*not_done*target_critic_value
        targets.to(self.device) 
        
        
       
        
         
        
        self.critic.train()
        
        self.critic_optimizer.zero_grad()
        
        critic_value = self.critic.forward(states, actions)
        
      
        
        loss = self.critic_criterion(critic_value, targets)
        
        loss.backward() 
        
        self.critic_optimizer.step() 
        
        self.critic.eval() 
        
        self.actor_optimizer.zero_grad() 
        
        self.actor.train() 
        
        mu = self.actor.forward(states)
        
        actor_loss = -self.critic.forward(states,mu)
        
        actor_loss = torch.mean(actor_loss)
        
        actor_loss.backward()
        
        self.actor_optimizer.step()
        
        self.update_target_weights(self.tau)
        
    def save_model(self):
        
        self.actor.save_checkpoint()
        
        self.critic.save_checkpoint()
        
        self.target_actor.save_checkpoint()
        
        self.target_critic.save_checkpoint()

    def load_model(self):
        
        self.actor.load_checkpoint()
        
        self.critic.load_checkpoint()
        
        self.target_actor.load_checkpoint()
        
        self.target_critic.load_checkpoint()
        
        
        
        
        
        
        


        
                   
        
        
        
        
        


        
        
       


               




