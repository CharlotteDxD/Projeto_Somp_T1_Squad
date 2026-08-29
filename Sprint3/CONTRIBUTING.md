# Como contribuir

## Histórico de commits

O trabalho de cada integrante precisa aparecer no histórico do repositório.
Isso é critério de avaliação e, mais que isso, é o registro de quem
construiu o quê.

### Configure sua identidade antes do primeiro commit

Se isso não estiver certo, seus commits aparecem com nome errado — ou pior,
atribuídos a outra pessoa.

```bash
git config user.name "Seu Nome Completo"
git config user.email "seu.email@fiap.com.br"
```

Confira com `git log --format='%an <%ae>'` que o nome saiu correto.

### Commite o seu próprio trabalho

Evite que uma pessoa suba o código de todo mundo — o histórico passa a
mostrar um só autor e o trabalho dos demais desaparece do registro. Se
alguém precisar subir código de outra pessoa, use `--author`:

```bash
git commit --author="Nome <email>" -m "..."
```

## Frentes por integrante

| Integrante | Frente | Arquivos principais |
|---|---|---|
| Anthony Prado Pereira | IoT e embarcados | `firmware/` |
| Charles Augusto Miranda da Silva | Cybersegurança · Produto | `core_app.py`, `core_audit.py`, `core_perfis.py`, `pagina_us01/us03`, `pagina_meu_equipamento.py` |
| Guilherme Araujo Pinto | Dados e estatística | `database/`, `data_science/`, `base_sompo_limpa.csv` |
| Gustavo Reatti Sela | Nuvem | `deploy/`, `api_telemetria.py`, `wsgi.py` |
| Rafael Gonçalves | Scrum Master · ML | `core_fusao.py`, `scripts/`, `pagina_desempenho_modelos.py` |

## Mensagens de commit

Uma linha, no imperativo, dizendo o que muda — não o que foi feito:

```
Adiciona validação de chave HMAC no boot do serviço
Corrige contador de tentativas que zerava antes do bloqueio
Documenta limitação do modelo XGBoost na base atual
```

Evite `update`, `ajustes`, `wip`, `correções` — daqui a um mês ninguém
sabe o que foi.

## Antes de commitar

**Nunca suba segredo.** O `.gitignore` já bloqueia os arquivos conhecidos
(`.chave_local`, `firmware/config.h`, `.env`), mas confira o que está indo:

```bash
git status
git diff --cached
```

Se um segredo já foi commitado, não basta apagar o arquivo no commit
seguinte — ele continua no histórico. Nesse caso, avise o time: a chave
precisa ser rotacionada.

**Verifique dado simulado sem identificação.** Toda tela alimentada por
dado gerado precisa exibir aviso. O script confere:

```bash
python scripts/auditoria_procedencia.py .
```

Sai com código 2 se houver dado exibido sem identificação. Zero crítico é
condição para a entrega.

**Confirme que os dois portais sobem:**

```bash
python -c "import app"
SOMPO_PERFIL=cliente python -c "import app"
```
