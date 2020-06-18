import math
from enum import Enum

from pydantic import validator
from typing import List, Optional
import numpy as np
from pydantic.types import constr

from anonymizer.utils.discrete_distribution import DiscreteDistribution, DiscreteDistributionModel
from ._base import MechanismModel


class RandomizedResponseMode(str, Enum):
    custom = "custom"
    coin = "coin"
    dp = "dp"


class RandomizedResponseParameters(MechanismModel):
    MECHANISM: constr(regex="^randomizedResponse$") = "randomizedResponse"
    values: List[str]
    mode: RandomizedResponseMode = RandomizedResponseMode.custom
    probability_distribution: Optional[DiscreteDistributionModel] = None  # RandomizedResponseMode.{custom, coin}
    epsilon: Optional[float] = None  # Only used for RandomizedResponseMode.dp
    coin_p: Optional[float] = None  # Only used for RandomizedResponseMode.coin
    default_value: Optional[str] = None

    @validator("probability_distribution", always=True)
    def distribution_size_matches(cls, v, values, **kwargs):
        if "values" not in values:
            raise ValueError("Missing required property: values")
        mode = values["mode"]
        if mode in (RandomizedResponseMode.custom, RandomizedResponseMode.coin):
            num_values = len(values["values"])
            if not isinstance(v, DiscreteDistributionModel) or v.shape() != num_values:
                raise ValueError("Size of probability distribution does not match values")
            return v
        else:
            return None

    @validator("epsilon", always=True)
    def epsilon_check(cls, v, values, **kwargs):
        mode = values["mode"]
        if mode == RandomizedResponseMode.dp:
            if v is None:
                raise ValueError("DP mode requires epsilon value")
            return v
        else:
            return None

    @validator("coin_p", always=True)
    def coin_p_check(cls, v, values, **kwargs):
        mode = values["mode"]
        if mode == RandomizedResponseMode.coin:
            if v is None:
                raise ValueError("Coin mode requires coin_p value")
            return v
        else:
            return None

    def build(self):
        if self.mode == RandomizedResponseMode.dp:
            return RandomizedResponse.with_dp(self.values, self.epsilon, self.default_value)
        elif self.mode == RandomizedResponseMode.coin:
            return RandomizedResponse.with_coin(self.values, self.coin_p, self.probability_distribution, self.default_value)
        return RandomizedResponse(self)

    class Config:
        # Make sure conditional requirements are adequately reflected.
        schema_extra = {
            "anyOf": [
                {"properties": {"mode": {"const": "custom"}}, "required": ["probabilityDistribution"]},
                {"properties": {"mode": {"const": "dp"}}, "required": ["epsilon"]},
                {"properties": {"mode": {"const": "coin"}}, "required": ["coinP"]},
            ]
        }


class RandomizedResponse:
    """
    The randomized response mechanisms anonymizes input by replacing it with a certain probability
    with a value drawn from a given probability distribution.

    See: "Using Randomized Response for Differential Privacy Preserving Data Collection" by Wang, Wu, and Hu
    http://csce.uark.edu/~xintaowu/publ/DPL-2014-003.pdf
    Section 4: POLYCHOTOMOUS ATTRIBUTE
    """

    def __init__(self, values, probability_distribution=None, **kwargs):
        """
        Initiates the randomized response mechanism.
        This mechanisms takes two mandatory parameters: `values` and `probability_distribution`.
        Alternatively, a `RandomizedResponseParameters` object can be passed.

        The `values` parameter defines the list of potential replacements to select from.
        The `probability_distribution` parameter can be either of the following three:
        1) An instance of `DiscreteDistribution`,
        2) A list of weights with `len(probability_distribution) == len(values)`,
        3) A matrix where each row represents the list of weights for an input value,
           i.e., `probability_distribution[i][j]` is the probability of outputting value j given value i as an input.
           The dimensions of the matrix are `len(values) x len(values)`.

        >>> mechanism = RandomizedResponse(['Yes', 'No'], [1, 0])
        >>> mechanism.anonymize('Yes')
        'Yes'
        >>> mechanism.anonymize('No')
        'Yes'

        The mechanisms allows to specify a third, optional parameter `default_value`.
        This mechanism usually requires the list of `values` to be exhaustive over all possible inputs.
        If `anonymize` is called with an unknown value, this mechanism may raise a ValueError.
        Specifying the `default_value` prevents this and returns the `default_value` in such cases.

        >>> mechanism = RandomizedResponse(['Yes', 'No'], [0, 1], default_value='<UNKNOWN>')
        >>> mechanism.anonymize('Yes')
        'No'
        >>> mechanism.anonymize('Foobar')
        '<UNKNOWN>'
        """

        if not isinstance(probability_distribution, DiscreteDistribution):
            parameters = (
                values
                if isinstance(values, RandomizedResponseParameters)
                else RandomizedResponseParameters(
                    values=values,
                    probability_distribution=DiscreteDistributionModel(weights=probability_distribution),
                    **kwargs
                )
            )
            probability_distribution = DiscreteDistribution(parameters.probability_distribution)
            values = parameters.values
            default_value = parameters.default_value
        else:
            default_value = kwargs["default_value"] if "default_value" in kwargs else None

        self.cum_distr = probability_distribution.to_cumulative()
        self.values = values
        self.default_value = default_value

    @classmethod
    def with_dp(cls, values, epsilon, default_value=None):
        """
        Instantiates a randomized response mechanism that is epsilon-differentially private.

        Let `t = len(values)`.
        This results in a probability of `e^epsilon / (t - 1 + e^epsilon) for revealing the true value,
        and a probability of `1 / (t - 1 + e^epsilon)` for each other value.
        """
        t = len(values)
        e_eps = math.exp(epsilon)
        denominator = t - 1 + e_eps
        p_ii = e_eps / denominator
        p_ij = 1 / denominator

        # Create a matrix filled with p_ij
        weights = np.full((t, t), p_ij)
        # Create a matrix with diagonal entries p_ii - p_ij
        diag = np.zeros((t, t))
        np.fill_diagonal(diag, p_ii - p_ij)
        # Sum the two matrices to obtain our result
        weights += diag
        d = DiscreteDistribution(weights)
        return RandomizedResponse(values, d, default_value=default_value)

    @classmethod
    def with_coin(cls, values, coin_p=0.5, probability_distribution=None, default_value=None):
        """
        Instantiates a randomized response mechanism that simulates the following experiment:
        1) Toss a coin (with heads having a probability `coin_p`, which defaults to 0.5).
        2) If heads, report true value.
        3) If tails, then throw another coin to randomly choose one element from `values`
           based on the `probability_distribution` (default is a uniform distribution).
           The probability distribution can be a list of weights.
           Alternatively, it can be a matrix where each row represents the list of weights for an input value,
           i.e., `probability_distribution[i][j]` is the probability of outputting value j given value i as an input.
        """
        if probability_distribution is None:
            d = DiscreteDistribution.uniform_distribution(len(values))
        else:
            d = DiscreteDistribution(probability_distribution)

        d_rr = d.with_rr_toss(coin_p)
        return RandomizedResponse(values, d_rr, default_value=default_value)

    def anonymize(self, input_value):
        """
        Anonymizes the given input parameter by generalizing it.
        If the input_value is unknown to the distribution and no `default_value` is set, it raises a ValueError.
        """
        try:
            input_idx = self.values.index(input_value)
        except ValueError as e:
            if self.default_value is not None:
                return self.default_value
            raise e
        output_idx = self.cum_distr.sample_element(input_idx)
        return self.values[output_idx]
