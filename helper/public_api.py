from public_api_sdk import (
    ApiKeyAuthConfig,
    PublicApiClient,
    PublicApiClientConfiguration,
)


def get_client():
    try:
        with open("config/.publicdotcom_key") as f:
            key = f.readline()
    except: #NOQA
        print("Error loading the key for public.com from the file .publicdotcom_key")
        return None
    return PublicApiClient(
        ApiKeyAuthConfig(api_secret_key=key),
        config=PublicApiClientConfiguration()
        )