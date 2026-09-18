# Versionamento e release

A versão do portal não é escolhida à mão. Ela sai das mensagens de commit, pelo
[python-semantic-release](https://python-semantic-release.readthedocs.io/) (PSR), rodando no
GitHub Actions a cada push para `main`.

## O fluxo

```text
PR para main ──► Quality Gate (quality.yml)
                   ├─ Lint, tipos e JavaScript   ruff · pyright · node --check
                   ├─ Testes                      unittest em 3.11, 3.12 e 3.13
                   └─ Migrations e semeadura      db upgrade · db check · init-db 2x

push para main ──► Release (release.yml)
                   ├─ quality: chama quality.yml (o mesmo gate do PR)
                   └─ release: needs quality
                        ├─ checkout com histórico e tags, fixado no SHA do push
                        ├─ PSR calcula a versão desde a última tag
                        ├─ atualiza pyproject.toml e CHANGELOG.md
                        ├─ commit "chore(release): vX.Y.Z", tag vX.Y.Z, push
                        └─ publica a GitHub Release
```

O gate não tem gatilho de push próprio. Um push para `main` o executa uma única vez, dentro do
Release, e o release só roda se o gate daquele mesmo commit passou.

## Como o número é decidido

O PSR encontra a última tag `vX.Y.Z` **alcançável a partir da `main`** e aplica o maior
incremento encontrado nos commits posteriores a ela:

| Commit | Incremento | Exemplo |
| --- | --- | --- |
| `fix:` / `perf:` | patch | 1.0.0 → 1.0.1 |
| `feat:` | minor | 1.0.1 → 1.1.0 |
| `BREAKING CHANGE:` no rodapé, ou `feat!:` | major | 1.1.0 → 2.0.0 |
| `docs`, `chore`, `test`, `ci`, `refactor`, `style`, `build` | nenhum | — |

A quantidade de commits não soma: dez `fix` geram um único patch. Commits fora do padrão
Conventional Commits são ignorados no cálculo e no changelog.

Num PR com squash merge, o **título do PR** vira o commit, e é ele que decide a versão.

## Regras

- **Não edite `project.version` nem o `CHANGELOG.md` à mão.** O release escreve os dois. As
  entradas novas entram abaixo da marca `<!-- versoes -->`; a 1.0.0, escrita à mão, fica no fim.
- **Não reescreva o histórico da `main` depois de uma release** (rebase, amend, push forçado).
  A tag passa a apontar para um commit fora da branch, e o PSR para de publicar (veja abaixo).
- Actions são pinadas por SHA completo, com a versão em comentário. O Dependabot
  (`.github/dependabot.yml`) propõe as atualizações num PR semanal com prefixo `ci`.
- O token do workflow só recebe `contents: write` no job de release.
- O release só conhece `main`. Um disparo manual (`workflow_dispatch`) em outra branch não faz nada.

## Conferir antes de empurrar

```powershell
$env:PYTHONUTF8 = "1"                  # sem isso o PSR lê o CHANGELOG em cp1252 e falha
git fetch --tags
semantic-release --noop version --print
```

A saída é a versão que sairia. `No release will be made` significa que nenhum commit desde a
última tag pede incremento. Se a última tag estiver fora da `main`, o sintoma também é esse
(veja abaixo).

## Quando a tag sai do histórico da `main`

**Sintoma:** há `fix`/`feat` novos, o workflow roda verde e nada é publicado. Localmente:

```text
1.0.0
No release will be made, 1.0.0 has already been released!
```

**Causa:** a tag existe, mas o commit dela não é ancestral da `main`. Sem tag alcançável, o PSR
recalcula a partir do zero, chega a uma versão que já existe e desiste. Foi o que aconteceu com a
`v1.0.0`: o release criou `6144b51` na `main` do GitHub, e o merge que unificou os históricos
(`7be83a5`) foi empurrado por cima, deixando `6144b51` órfão.

**Diagnóstico:**

```powershell
git fetch --tags
git merge-base --is-ancestor "v1.0.0^{commit}" main; $LASTEXITCODE   # 1 = fora da main
```

**Correção:** mover a tag para o commit da `main` com o mesmo conteúdo da versão publicada. Para
a `v1.0.0` esse commit é `7be83a5`. A árvore dele é idêntica à de `f9f7d63`, a base do release, e
ele ainda deixa o histórico antigo (PRs #1 a #7) antes da 1.0.0.

```powershell
git tag -f -a v1.0.0 7be83a5 -m "v1.0.0"
git push --force origin v1.0.0
```

Depois disso, `semantic-release --noop version --print` deve mostrar a próxima versão. A GitHub
Release da `v1.0.0` continua existindo; ela passa a apontar para a tag movida.
