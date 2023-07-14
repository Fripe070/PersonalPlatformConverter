from .abc import AbstractAPI, AbstractOAuthAPI

APIInterface = AbstractAPI | AbstractOAuthAPI