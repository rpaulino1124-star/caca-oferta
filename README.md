# OFERTIVA AI + CAÇA OFERTA

Operação open source para afiliados Shopee com dashboard mobile, pontuação heurística, API oficial de afiliados, roteiros, vídeos MP4, narração em português e divulgação Telegram.

## Funcionalidades reais

- Painel web responsivo em português: cadastre produtos e seu link próprio de afiliado, calcule o valor estimado da comissão por unidade, gere um roteiro e solicite vídeo.
- Dados cadastrados no navegador são locais, não sincronizados entre dispositivos.
- Workflow GitHub Actions: 3 consultas por dia à API Shopee, no máximo 1 nova oferta por execução, com histórico anti-repetição em data/posted.json.
- API da Shopee Affiliate: productOfferV2 por GraphQL, assinatura SHA256 usando credenciais aprovadas.
- Python + Pillow + FFmpeg: vídeo vertical MP4 de aproximadamente 12s a partir de imagens autorizadas, com narração edge-tts quando disponível.
- Google Gemini opcional: texto em português sem inventar características. Sem chave, roteiro factual baseado em template.
- Telegram: envio automático do vídeo com link rastreado do afiliado e identificação de publicidade (quando canal e bot estão corretamente configurados).
- Issue do GitHub: crie um produto no dashboard e selecione "Solicitar vídeo"; no GitHub, confirme "Submit new issue". Só issues do dono acionam a criação de vídeo.
- Rota legada do Telegram agora protegida por ADMIN_API_KEY.

## Credenciais necessárias

Acesse o repositório GitHub -> Settings -> Secrets and variables -> Actions -> New repository secret.

Configure:
1. SHOPEE_APP_ID: ID da sua aplicação aprovado no Programa de Afiliados da Shopee.
2. SHOPEE_APP_SECRET: Secret aprovado na Shopee.
3. TELEGRAM_BOT_TOKEN: token do seu próprio bot Telegram.
4. TELEGRAM_CHANNEL: identificador @seu_canal ou ID numérico do canal no qual o bot é administrador.
5. GEMINI_API_KEY: opcional, para gerar copy com IA.

Nunca compartilhe tokens em chats nem os adicione a arquivos públicos. ADMIN_API_KEY é uma chave opcional do próprio servidor Vercel para proteger chamadas administrativas, não deve ser exposta ao navegador em variáveis NEXT_PUBLIC.

Sem credenciais, a API não é consultada e não são simuladas postagens. Ainda é possível gerar vídeos a partir de issues do dono com imagens CDN de produtos válidos; o MP4 ficará disponível em Actions > Artifacts.

## Primeiro vídeo usando o celular

1. Abra o painel, cadastre nome, preço, link pessoal de afiliado e pelo menos uma URL direta da imagem hospedada pela Shopee.
2. Clique em "Solicitar vídeo".
3. Na página de criação da issue GitHub, clique em "Submit new issue".
4. Abra Actions > Ofertiva AI - vídeos e ofertas; após o workflow, o vídeo estará nos artifacts, ou será enviado ao Telegram se configurado.
5. Publique o arquivo no Shopee Vídeo com a associação do produto dentro do aplicativo Shopee.

## Executar no computador

- Painel: Node.js 20+, comando "npm install" seguido de "npm run dev".
- Gerador local: Python 3.11+ e FFmpeg. Instale "python -m pip install -r automation/requirements.txt" e execute "python automation/worker.py".
- Testes: "python -m unittest discover -s automation -p test_*.py".
- Você pode cadastrar uma lista validada de produtos em data/products.json, mas o agendador sem API não encontra ofertas sozinho.

## Limites

A API oficial de afiliados para pesquisa e links NÃO é autorização para publicar no Shopee Vídeo. O envio ao Shopee Vídeo permanece assistido, com associação de produto feita no app, até obter um meio oficial/autorizado para o seu tipo de conta. Não há falsificação de demonstrações de uso ou garantia de comissão. Imagens devem ter direito de utilização publicitária. Não usamos automações que burlem CAPTCHA, login ou sistemas privados.

Referência oficial: https://open-api.affiliate.shopee.com.br/explorer
