## O que muda

<!-- Uma ou duas frases. O porquê importa mais que o quê. -->

## Checklist

- [ ] O título segue Conventional Commits (`feat(admin): ...`, `fix(copa): ...`).
      Num squash merge ele vira o commit e decide a próxima versão.
- [ ] `ruff check .`, `pyright` e a suíte passam localmente.
- [ ] Mudou `app/models.py`? A migration está no PR.
- [ ] Mudou `app/seed.py`? Continua aditivo: só acrescenta, nunca altera registro existente.
- [ ] Decisão de arquitetura nova? Registrada em `docs/DECISIONS.md`.

Não edite a versão no `pyproject.toml` nem o `CHANGELOG.md`: o workflow de
release escreve os dois.
