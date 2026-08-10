# Avisos de terceiros

## Fedra Sans Pro

Os arquivos em `app/static/font/` são da família **Fedra Sans Pro**, uma fonte
comercial licenciada. Eles estão versionados aqui para que o portal funcione sem
depender de CDN — o que também é o que permite manter a Content-Security-Policy
sem nenhuma origem externa.

Antes de publicar este repositório fora da organização, ou de servir a aplicação
em um domínio público, confirme com quem detém a licença se ela cobre:

- distribuição dos arquivos em repositório de código;
- entrega por servidor web para navegadores de terceiros.

Se a licença não cobrir esses usos, substitua a família por uma de licença aberta
e ajuste a pilha em `styles.css`. Todas as regras de `font-family` já declaram
alternativas de sistema, então a troca não quebra o layout.
