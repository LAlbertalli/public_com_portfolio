from public_api_sdk import PublicApiClient, PublicApiClientConfiguration, ApiKeyAuthConfig

def get_client():
    try:
        with open(".publicdotcom_key") as f:
            key = f.readline()
    except:
        print("Error loading the key for public.com from the file .publicdotcom_key")
        return None
    return PublicApiClient(
        ApiKeyAuthConfig(api_secret_key=key),
        config=PublicApiClientConfiguration()
        )
