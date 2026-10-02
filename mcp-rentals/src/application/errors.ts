import { error_codes } from '../contracts/responses.js';

const messages: Record<string, string> = {
  invalid_input: 'Argumentos inválidos para esta origem.', unsupported_capability: 'Esta origem não oferece essa capacidade.', not_installed: 'Dependências da origem não instaladas.', blocked: 'O site bloqueou a consulta; nenhum desafio foi contornado.', rate_limited: 'Consultas limitadas pelo site; nenhuma repetição automática.', http_error: 'Falha HTTP na origem.', invalid_content: 'Resposta não corresponde ao conteúdo esperado.', tls_error: 'Falha de verificação TLS.', timeout: 'Tempo limite da consulta excedido.', cancelled: 'Consulta cancelada.', output_limit: 'Resultado excedeu o limite de tamanho.', invalid_output: 'Resposta do worker fora do contrato.', worker_error: 'Falha de execução da origem.', shutdown: 'Servidor em encerramento.',
};
/** Never expose exception strings, stderr, configuration or upstream response bodies. */
export function normalize_error(error: unknown) {
  const candidate = error instanceof Error ? error.message : '';
  const parsed = error_codes.safeParse(candidate);
  const code = parsed.success ? parsed.data : 'worker_error';
  return {code, message: messages[code]!};
}
