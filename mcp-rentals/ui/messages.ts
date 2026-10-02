const errorMessages: Record<string, string> = {
  invalid_input: 'Os filtros informados são inválidos. Revise os campos.',
  unsupported_capability: 'Esta operação não está disponível para esta imobiliária.',
  not_installed: 'Este provedor não está instalado neste ambiente.',
  blocked: 'O site bloqueou a consulta.',
  rate_limited: 'O provedor limitou as consultas. Tente novamente mais tarde.',
  http_error: 'Falha de comunicação com o provedor.',
  invalid_content: 'O provedor retornou dados inválidos.',
  tls_error: 'Não foi possível verificar a conexão segura.',
  timeout: 'A consulta excedeu o tempo limite.',
  cancelled: 'A consulta foi cancelada.',
  output_limit: 'A resposta do provedor excedeu o limite permitido.',
  invalid_output: 'A resposta do provedor tem um formato inválido.',
  worker_error: 'O provedor falhou ao processar a consulta.',
  shutdown: 'O servidor está encerrando.',
};

export function errorMessage(code: unknown): string {
  if (typeof code !== 'string') return 'Não foi possível concluir a operação.';
  return errorMessages[code] ?? 'Não foi possível concluir a operação.';
}

export function errorFrom(value: unknown): string {
  if (!isRecord(value)) return 'Não foi possível concluir a operação.';
  return errorMessage(value.code);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}
