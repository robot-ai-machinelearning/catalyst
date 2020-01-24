import math

import torch
import torch.nn as nn
import torch.nn.functional as F


class NoisyLinear(nn.Linear):
    def __init__(self, features_in, features_out, sigma_init=0.017, bias=True):
        super().__init__(features_in, features_out, bias=bias)
        self.sigma_weight = nn.Parameter(
            torch.Tensor(features_out, features_in).fill_(sigma_init)
        )
        self.register_buffer(
            "epsilon_weight", torch.zeros(features_out, features_in)
        )
        if bias:
            self.sigma_bias = nn.Parameter(
                torch.Tensor(features_out).fill_(sigma_init)
            )
            self.register_buffer("epsilon_bias", torch.zeros(features_out))
        self.reset_parameters()

    def reset_parameters(self):
        std = math.sqrt(3 / self.features_in)
        nn.init.uniform(self.weight, -std, std)
        nn.init.uniform(self.bias, -std, std)

    def forward(self, input):
        torch.randn(self.epsilon_weight.size(), out=self.epsilon_weight)
        bias = self.bias
        if bias is not None:
            torch.randn(self.epsilon_bias.size(), out=self.epsilon_bias)
            bias = bias + self.sigma_bias * self.epsilon_bias
        return F.linear(
            input, self.weight + self.sigma_weight * self.epsilon_weight, bias
        )


class NoisyFactorizedLinear(nn.Linear):
    """
    NoisyNet layer with factorized gaussian noise

    N.B. torch.Linear already initializes weight and bias to
    """

    def __init__(self, features_in, features_out, sigma_zero=0.4, bias=True):
        super().__init__(features_in, features_out, bias=bias)
        sigma_init = sigma_zero / math.sqrt(features_in)
        self.sigma_weight = nn.Parameter(
            torch.Tensor(features_out, features_in).fill_(sigma_init)
        )
        self.register_buffer("epsilon_input", torch.zeros(1, features_in))
        self.register_buffer("epsilon_output", torch.zeros(features_out, 1))
        if bias:
            self.sigma_bias = nn.Parameter(
                torch.Tensor(features_out).fill_(sigma_init)
            )

    def forward(self, input):
        torch.randn(self.epsilon_input.size(), out=self.epsilon_input)
        torch.randn(self.epsilon_output.size(), out=self.epsilon_output)

        func = lambda x: torch.sign(x) * torch.sqrt(torch.abs(x))  # noqa: E731
        eps_in = func(self.epsilon_input)
        eps_out = func(self.epsilon_output)

        bias = self.bias
        if bias is not None:
            bias = bias + self.sigma_bias * eps_out.t()
        noise_v = torch.mul(eps_in, eps_out)
        return F.linear(input, self.weight + self.sigma_weight * noise_v, bias)
