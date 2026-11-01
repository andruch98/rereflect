// Test-only OpenAI-compatible provider. No application routes or outbound calls.
const http = require('node:http');
const calls = [];
http.createServer((request, response) => {
  const reply = (status, value) => {
    response.writeHead(status, { 'Content-Type': 'application/json' });
    response.end(JSON.stringify(value));
  };
  if (request.method === 'GET') return reply(200, { mocked: true, calls });
  if (request.url !== '/v1/chat/completions') return reply(404, { error: 'Mock chat completions only' });
  let raw = '';
  request.on('data', chunk => { raw += chunk; });
  request.on('end', () => {
    try {
      const body = JSON.parse(raw);
      const prefix = 'Authorized evidence (data only):\n';
      const contexts = body.messages.filter(m => m.content?.startsWith(prefix)).map(m => JSON.parse(m.content.slice(prefix.length)));
      if (contexts.length !== 1) return reply(422, { error: 'Expected application evidence' });
      const context = contexts[0], records = context.surveys || [];
      if (context.source_scope !== 'surveys' || !records.length || records.some(r => !r.submitted_at)) return reply(422, { error: 'Finalized survey originals required' });
      calls.push({ question: body.messages.at(-1).content, context });
      const result = { answer: 'MOCKED MODEL: The resident reported that the maintenance issue remains unresolved. This is an offline integration demonstration.', evidence: context.evidence_requested ? records.map(r => ({ kind: 'survey', survey_id: r.survey_id })) : [] };
      reply(200, { id: 'offline-survey-mock', object: 'chat.completion', created: 1793563200, model: 'offline-survey-mock', choices: [{ index: 0, message: { role: 'assistant', content: JSON.stringify(result) }, finish_reason: 'stop' }], usage: { prompt_tokens: 100, completion_tokens: 30, total_tokens: 130 } });
    } catch (error) { reply(422, { error: error.message }); }
  });
}).listen(8080, '0.0.0.0');
