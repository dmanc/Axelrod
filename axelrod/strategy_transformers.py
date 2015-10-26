
"""
Strategy Transformers -- class decorators that transform the behavior of any
strategy.

See the various Meta strategies for another type of transformation.
"""

import random
from types import FunctionType

from .actions import Actions, flip_action
from .random_ import random_choice

C, D = Actions.C, Actions.D

# Note: After a transformation is applied,
# the player's history is overwritten with the modified history
# just like in the noisy tournament case
# This can lead to unexpected behavior, such as when
# FlipTransform is applied to Alternator

def generic_strategy_wrapper(player, opponent, proposed_action, *args, **kwargs):
    """
    Strategy wrapper functions should be of the following form.

    Parameters
    ----------
    player: Player object or subclass (self)
    opponent: Player object or subclass
    proposed_action: an axelrod.Action, C or D
        The proposed action by the wrapped strategy
        proposed_action = Player.strategy(...)
    args, kwargs:
        Any additional arguments that you need.

    Returns
    -------
    action: an axelrod.Action, C or D

    """

    # This example just passes through the proposed_action
    return proposed_action

def StrategyTransformerFactory(strategy_wrapper, wrapper_args=(),
                               wrapper_kwargs={}, name_prefix=None):
    """Modify an existing strategy dynamically by wrapping the strategy
    method with the argument `strategy_wrapper`.

    Parameters
    ----------
    strategy_wrapper: function
        A function of the form `strategy_wrapper(player, opponent, proposed_action, *args, **kwargs)`
        Can also use a class that implements
            def __call__(self, player, opponent, action)
    wrapper_args: tuple
        Any arguments to pass to the wrapper
    wrapper_kwargs: dict
        Any keyword arguments to pass to the wrapper
    name_prefix: string, "Transformed "
        A string to prepend to the strategy and class name
    """

    # Create a function that applies a wrapper function to the strategy method
    # of a given class
    def decorate(PlayerClass, name_prefix=name_prefix):
        """
        Parameters
        ----------
        PlayerClass: A subclass of axelrod.Player, e.g. Cooperator
            The Player Class to modify
        name_prefix: str
            A string to prepend to the Player and Class name

        Returns
        -------
        new_class, class object
            A class object that can create instances of the modified PlayerClass
        """

        # Define the new strategy method, wrapping the existing method
        # with `strategy_wrapper`
        def strategy(self, opponent):
            # Is the original strategy method a static method?
            if isinstance(PlayerClass.__dict__["strategy"], staticmethod):
                proposed_action = PlayerClass.strategy(opponent)
            else:
                proposed_action = PlayerClass.strategy(self, opponent)
            # Apply the wrapper
            return strategy_wrapper(self, opponent, proposed_action,
                                    *wrapper_args, **wrapper_kwargs)

        # Define a new class and wrap the strategy method
        # Modify the PlayerClass name
        new_class_name = PlayerClass.__name__
        name = PlayerClass.name
        if name_prefix:
            # Modify the Player name (class variable inherited from Player)
            new_class_name = name_prefix + PlayerClass.__name__
            # Modify the Player name (class variable inherited from Player)
            name = name_prefix + ' ' + PlayerClass.name
        # Dynamically create the new class
        new_class = type(new_class_name, (PlayerClass,),
                         {"name": name, "strategy": strategy})
        return new_class
    return decorate

def flip_wrapper(player, opponent, action):
    """Applies flip_action at the class level."""
    return flip_action(action)

FlipTransformer = StrategyTransformerFactory(flip_wrapper, name_prefix="Flipped")

def noisy_wrapper(player, opponent, action, noise=0.05):
    """Applies flip_action at the class level."""
    r = random.random()
    if r < noise:
        return flip_action(action)
    return action

def NoisyTransformer(noise, name_prefix="Noisy"):
    """Creates a function that takes an axelrod.Player class as an argument
    and alters the play of the Player in the following way. The player's
    intended action is flipped with probability noise."""

    return StrategyTransformerFactory(noisy_wrapper,
                                      wrapper_args=(noise,),
                                      name_prefix=name_prefix)

def forgiver_wrapper(player, opponent, action, p):
    """If a strategy wants to defect, flip to cooperate with the given
    probability."""
    if action == D:
        return random_choice(p)
    return C

def ForgiverTransformer(p, name_prefix="Forgiving"):
    """Creates a function that takes an axelrod.Player class as an argument
    and alters the play of the Player in the following way. The player's
    defections are flipped with probability p."""

    return StrategyTransformerFactory(forgiver_wrapper, wrapper_args=(p,),
                                      name_prefix=name_prefix)

def initial_sequence(player, opponent, action, initial_seq):
    """Play the moves in `seq` first (must be a list), ignoring the strategy's
    moves until the list is exhausted."""

    index = len(player.history)
    if index < len(initial_seq):
        return initial_seq[index]
    return action

## Defection initially three times
def InitialTransformer(seq=None):
    """Creates a function that takes an axelrod.Player class as an argument
    and alters the play of the Player in the following way. The player starts
    with the actions in the argument seq and then proceeds to play normally."""

    if not seq:
        seq = [D] * 3
    transformer = StrategyTransformerFactory(initial_sequence,
                                             wrapper_args=(seq,))
    return transformer

def final_sequence(player, opponent, action, seq):
    """Play the moves in `seq` first, ignoring the strategy's moves until the
    list is exhausted."""

    length = player.tournament_attributes["length"]

    if length < 0: # default is -1
        return action

    index = length - len(player.history)
    if index <= len(seq):
        return seq[-index]
    return action

def FinalTransformer(seq=None):
    """Creates a function that takes an axelrod.Player class as an argument
    and alters the play of the Player in the following way. If the tournament
    length is known, the play ends with the actions in the argument seq.
    Otherwise the player's actions are unaltered. """

    if not seq:
        seq = [D] * 3
    transformer = StrategyTransformerFactory(final_sequence,
                                             wrapper_args=(seq,))
    return transformer

# Strategy wrapper as a class example
class RetaliationWrapper(object):
    """Enforces the TFT rule that the opponent pay back a defection with a
    cooperation for the player to stop defecting."""
    def __init__(self):
        self.is_retaliating = False

    def __call__(self, player, opponent, action):
        if len(player.history) == 0:
            return action
        if opponent.history[-1] == D:
            self.is_retaliating = True
        if self.is_retaliating:
            if opponent.history[-1] == C:
                self.is_retaliating = False
                return C
            return D
        return action

def RetailiateUntilApologyTransformer(name_prefix="RUA"):
    """Creates a function that takes an axelrod.Player class as an argument
    and alters the play of the Player in the following way. If the opponent
    defects, the player will retaliate with defections until the opponent
    cooperates. Otherwise the player's actions are unaltered."""

    strategy_wrapper = RetaliationWrapper()
    return StrategyTransformerFactory(strategy_wrapper, name_prefix=name_prefix)

def history_track_wrapper(player, opponent, action):
    """Wrapper to track a player's history in a variable `._recorded_history`."""
    try:
        player._recorded_history.append(action)
    except AttributeError:
        player._recorded_history = [action]
    return action

TrackHistoryTransformer = StrategyTransformerFactory(history_track_wrapper,
                                        name_prefix="HistoryTracking")