import falcon

from requests_oauthlib import OAuth2Session

from config import AppConfig

from auth import create_access_token, get_current_user


class LoginResource:
    def __init__(self, config: AppConfig):
        self.config = config.config

    async def on_get(self, req, resp):
        config = self.config
        try:            
            get_current_user(req, config)
            raise falcon.HTTPFound(location='/')
        except (falcon.HTTPForbidden, falcon.HTTPUnauthorized):
            oauth = OAuth2Session(
                config['client_id'], redirect_uri=config['redirect_url'], scope="profile")
            authorization_url, _ = oauth.authorization_url(
                config['oauth_authorize_url'])
            raise falcon.HTTPFound(location=authorization_url)


class OAuthCallbackResource:

    def __init__(self, config: AppConfig):
        self.config = config

    async def on_get(self, req, resp):
        code = req.params.get('code')
        state = req.params.get('state')
        config = self.config.config
        if not code or not state:
            raise falcon.HTTPBadRequest(title='Missing Code or State')

        # Get token and user info
        oauth = OAuth2Session(
            config['client_id'], state=state, redirect_uri=config['redirect_url'])
        token = oauth.fetch_token(
            config['oauth_token_url'],
            client_secret=config['client_secret'],
            authorization_response=str(req.url)
        )
        response = oauth.get(config['oauth_user_api_url'])
        user_data = response.json()

        access_token = create_access_token(data={"user": user_data}, config=self.config)

        login_url = config['login_url'] + "?access_token=" + access_token
        raise falcon.HTTPFound(location=login_url)


class LogoutResource:
    async def on_get(self, req, resp):
        raise falcon.HTTPFound(location='/login')
