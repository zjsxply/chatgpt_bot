import httpx
from config import PROXY


def _send_to_openai(endpoint_url: str, method='post'):
    async def send_to_openai(api_key: str, timeout: float, payload: dict) -> httpx.Response:
        """
        Send a request to openai.
        :param api_key: your api key
        :param timeout: timeout in seconds
        :param payload: the request body, as detailed here: https://beta.openai.com/docs/api-reference
        """
        async with httpx.AsyncClient(proxies=PROXY) as client:
            if method == 'post':
                r = await client.post(
                    url=endpoint_url,
                    json=payload,
                    headers={"content_type": "application/json", "Authorization": f"Bearer {api_key}"},
                    timeout=timeout,
                )
                return r.json()
            else:
                r = await client.get(
                    url=endpoint_url,
                    params=payload,
                    headers={"content_type": "application/json", "Authorization": f"Bearer {api_key}"},
                    timeout=timeout,
                )
                return r.json()
    
    return send_to_openai


complete = _send_to_openai("https://api.openai.com/v1/completions")
generate_img = _send_to_openai("https://api.openai.com/v1/images/generations")
embeddings = _send_to_openai("https://api.openai.com/v1/embeddings")
chat_complete = _send_to_openai("https://api.openai.com/v1/chat/completions")
credit_grants = _send_to_openai("https://api.openai.com/dashboard/billing/credit_grants", "get")
subscription = _send_to_openai("https://api.openai.com/v1/dashboard/billing/subscription", "get")
usage = _send_to_openai("https://api.openai.com/v1/dashboard/billing/usage", "get")