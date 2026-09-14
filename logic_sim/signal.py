"""
signal.py — Signal type for digital logic simulation.

Design decision: We use three-valued logic (0, 1, X) instead of just binary.
UNKNOWN (X) represents uninitialized wires, flip-flop states before the first
clock edge, or propagated uncertainty. This matters because silently defaulting
to 0 would hide real bugs: a circuit where an output depends on an uninitialized
flip-flop state would appear to work but would produce non-deterministic
behavior on real hardware.
"""

from enum import Enum


class Signal(Enum):
    """
    Three-valued signal type used throughout the simulator.

    Values:
        LOW     (0): Logic low / Boolean False
        HIGH    (1): Logic high / Boolean True
        UNKNOWN (X): Uninitialized, indeterminate, or propagated unknown state.
                     Uninitialized wires and flip-flop states default to UNKNOWN.
    """
    LOW = 0
    HIGH = 1
    UNKNOWN = "X"

    def __repr__(self) -> str:
        return f"Signal.{self.name}"

    def __str__(self) -> str:
        if self == Signal.LOW:
            return "0"
        elif self == Signal.HIGH:
            return "1"
        else:
            return "X"

    @staticmethod
    def from_int(value: int) -> "Signal":
        """
        Convert an integer (0 or 1) to a Signal.

        Args:
            value: 0 or 1

        Returns:
            Signal.LOW for 0, Signal.HIGH for 1

        Raises:
            ValueError: If value is not 0 or 1.
        """
        if value == 0:
            return Signal.LOW
        elif value == 1:
            return Signal.HIGH
        else:
            raise ValueError(f"Cannot convert {value!r} to Signal; expected 0 or 1.")

    @staticmethod
    def from_str(s: str) -> "Signal":
        """
        Parse a signal from a string representation.

        Args:
            s: "0", "1", or "X" (case-insensitive for X)

        Returns:
            Corresponding Signal value.

        Raises:
            ValueError: If the string is not recognizable.
        """
        s = s.strip()
        if s == "0":
            return Signal.LOW
        elif s == "1":
            return Signal.HIGH
        elif s.upper() == "X":
            return Signal.UNKNOWN
        else:
            raise ValueError(f"Cannot parse {s!r} as Signal; expected '0', '1', or 'X'.")

    def is_known(self) -> bool:
        """Return True if the signal has a definite value (LOW or HIGH)."""
        return self != Signal.UNKNOWN

    def invert(self) -> "Signal":
        """
        Return the logical NOT of this signal.

        UNKNOWN inverted is still UNKNOWN (we cannot determine the complement
        of an indeterminate value).
        """
        if self == Signal.LOW:
            return Signal.HIGH
        elif self == Signal.HIGH:
            return Signal.LOW
        else:
            return Signal.UNKNOWN
