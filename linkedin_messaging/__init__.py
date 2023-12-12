"""An unofficial API for interacting with LinkedIn Messaging"""

from .api_objects import URN
from .linkedin import ChallengeException, LinkedInMessaging

__all__ = ("ChallengeException", "LinkedInMessaging", "URN")
