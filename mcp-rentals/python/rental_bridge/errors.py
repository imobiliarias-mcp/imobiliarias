"""Safe local error codes; external responses and secrets never become messages."""

MESSAGES = {
    'invalid_input': 'Argumentos inválidos para esta origem.',
    'unsupported_capability': 'Esta origem não oferece a capacidade solicitada.',
    'not_installed': 'Dependências desta origem não estão instaladas.',
    'blocked': 'O site bloqueou a consulta; nenhum desafio foi contornado.',
    'rate_limited': 'O site limitou as consultas. Não há repetição automática.',
    'http_error': 'A origem respondeu com falha HTTP ou redirecionamento não permitido.',
    'invalid_content': 'A resposta não corresponde ao conteúdo esperado.',
    'tls_error': 'Falha na verificação TLS da origem.',
    'worker_error': 'Falha ao executar a consulta desta origem.',
    'output_limit': 'Resposta da origem excedeu o limite de tamanho.',
}


class BridgeError(RuntimeError):
    """Carries only a normalized code, never an upstream response or credential."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def safe_error(error):
    """Return a bounded, local error envelope for any execution exception."""
    if isinstance(error, BridgeError):
        return {'code': error.code, 'message': MESSAGES[error.code]}
    if isinstance(error, (ModuleNotFoundError, ImportError)):
        return {'code': 'not_installed', 'message': MESSAGES['not_installed']}
    return {'code': 'worker_error', 'message': MESSAGES['worker_error']}
