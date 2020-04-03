import math
from anonymizer.utils.discrete_distribution import DiscreteDistribution


class RandomizedResponse:
    """
    The randomized response mechanisms anonymizes input by replacing it with a certain probability
    with a value drawn from a given probability distribution.

    See: "Using Randomized Response for Differential Privacy Preserving Data Collection" by Wang, Wu, and Hu
    http://csce.uark.edu/~xintaowu/publ/DPL-2014-003.pdf
    Section 4: POLYCHOTOMOUS ATTRIBUTE
    """

    def __init__(self, values, probability_distribution, default_value=None):
        """
        Initiates the randomized response mechanism.
        This mechanisms takes two mandatory parameters: `values` and `probability_distribution`.

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
            probability_distribution = DiscreteDistribution(probability_distribution)

        if len(values) != len(probability_distribution):
            raise ValueError("Values and distribution must be of the same size.")
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

        # TODO: n^2 operation
        weights = []
        for i in range(t):
            weights.append([])
            for j in range(t):
                if i == j:
                    weights[i].append(p_ii)
                else:
                    weights[i].append(p_ij)
        d = DiscreteDistribution(weights)
        return RandomizedResponse(values, d, default_value)

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
        return RandomizedResponse(values, d_rr, default_value)

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
