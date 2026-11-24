# Publicação do serviço de ingestão na AWS

Guia completo, de uma instância vazia ao serviço recebendo telemetria de
campo. Tempo estimado: 15 minutos.

---

## O que vai ao ar

Uma aplicação Python única que recebe as leituras dos dispositivos,
valida o formato, confere a assinatura, calcula o score de risco e expõe
as consultas usadas pela plataforma. Não depende de banco de dados para
operar — as leituras são persistidas em arquivo.

```
dispositivo ──POST──▶ serviço de ingestão ──▶ arquivo de leituras
                            │
                            ├─ valida formato e faixas
                            ├─ confere assinatura
                            ├─ barra reenvio
                            └─ calcula score (perfil + exposição)
                                     │
                       plataforma ◀──┘  GET último / série / frota
```

---

## 1 · Instância

| Item | Valor | Por quê |
|---|---|---|
| Tipo | `t2.micro` ou `t3.micro` | Suficiente: poucas leituras por segundo, trabalho curto por requisição |
| Sistema | Ubuntu 22.04 LTS | Python 3.10 já disponível |
| Disco | 8 GB | O arquivo de leituras cresce ~1 MB por 10 mil leituras |

### Grupo de segurança

| Tipo | Porta | Origem | Observação |
|---|---|---|---|
| SSH | 22 | **seu IP apenas** | Nunca `0.0.0.0/0` |
| HTTP | 80 | `0.0.0.0/0` | Entrada dos dispositivos |

Publicar na **porta 80** não é preferência: redes corporativas e de campo
costumam bloquear saída em portas altas, e o dispositivo falharia de forma
silenciosa — sem erro visível, apenas sem dado chegando.

### Endereço fixo

O endereço público de uma instância **muda a cada parada e reinício**. Sem
endereço fixo, o dispositivo já gravado passa a apontar para o vazio depois
de qualquer manutenção.

```bash
aws ec2 allocate-address --domain vpc
aws ec2 associate-address --instance-id <id> --allocation-id <alloc>
```

Enquanto associado a uma instância em execução, não há custo.

---

## 2 · Publicação

Do computador local:

```bash
scp -i <chave.pem> -r . ubuntu@<endereco>:/tmp/sompo
ssh -i <chave.pem> ubuntu@<endereco>
```

Na instância:

```bash
sudo bash /tmp/sompo/deploy/bootstrap_ec2.sh
```

O script instala as dependências, cria o ambiente isolado, **gera uma chave
de assinatura**, registra o serviço para iniciar junto com o sistema e
verifica que ele responde.

> A chave gerada é exibida uma única vez. Anote: é o mesmo valor que vai no
> arquivo de configuração do dispositivo.

O script é idempotente — pode ser executado de novo para atualizar o código
sem refazer a configuração nem perder as leituras já gravadas.

---

## 3 · Verificação

```bash
bash deploy/verificar.sh http://<endereco>:80
```

Nove verificações: disponibilidade, formato aceito, exigência de
assinatura, leitura processada, score calculado, recusa de leitura fora de
faixa, bloqueio de reenvio e as duas consultas. Sai com código 0 apenas se
todas passarem.

Diagnóstico rápido, direto na instância:

```bash
systemctl status sompo-api
journalctl -u sompo-api -f
curl http://localhost/whoami
```

---

## 4 · Ligar as duas pontas

### Plataforma

```bash
# Windows PowerShell
$env:SOMPO_API_BASE = "http://<endereco>:80"
streamlit run app.py
```

Conferir em **Menu → Infraestrutura → Estado do serviço**: as três
verificações passam a exibir latência medida.

### Dispositivo

No arquivo de configuração (`firmware/config_exemplo.h`, salvo como
`config.h`):

```c
#define API_HOST    "<endereco>"
#define API_PORT    80
#define HMAC_KEY    "<a chave gerada pelo bootstrap>"
```

A chave precisa ser **idêntica** à do arquivo `/etc/sompo-predict.env` na
instância. Divergência resulta em recusa por assinatura inválida — código
401 no log, e nenhuma leitura registrada.

---

## 5 · Uma restrição de arquitetura

O serviço mantém em memória a última leitura de cada equipamento, a série
recente, o controle de reenvio e o estabilizador do sinalizador.

**Por isso roda com um único processo** (`--workers 1 --threads 8`, já
configurado). Com vários processos, cada um teria sua própria cópia desse
estado: a mesma consulta devolveria respostas diferentes conforme o
processo sorteado, o controle de reenvio deixaria passar duplicatas e o
sinalizador oscilaria. O sintoma se parece com instabilidade de rede e
custa horas de diagnóstico.

Um processo com oito threads atende o volume desta aplicação com folga. Se
o volume um dia exigir mais processos, o estado precisa migrar para
armazenamento compartilhado **antes** de aumentar o número de workers.

O estado em memória é reconstruído a partir do arquivo de leituras a cada
reinício, então manutenção não zera o painel.

---

## 6 · Operação

| Ação | Comando |
|---|---|
| Reiniciar | `sudo systemctl restart sompo-api` |
| Parar | `sudo systemctl stop sompo-api` |
| Acompanhar | `journalctl -u sompo-api -f` |
| Últimos 50 registros | `journalctl -u sompo-api -n 50 --no-pager` |
| Atualizar código | reenviar os arquivos e rodar o bootstrap de novo |
| Estatísticas | `curl http://localhost/telemetria/v1/health` |

### Onde ficam as coisas

```
/opt/sompo-predict/                     aplicação
/opt/sompo-predict/telemetria_ingerida.csv   leituras persistidas
/etc/sompo-predict.env                  configuração e chaves (chmod 600)
/etc/systemd/system/sompo-api.service   definição do serviço
```

### Segurança

- Chaves ficam em `/etc/sompo-predict.env`, com permissão 600 e fora do
  repositório. Chave versionada é chave vazada.
- Uma chave **por dispositivo** — comprometer um não compromete os demais.
- O serviço roda como usuário comum, com `NoNewPrivileges`,
  `ProtectSystem` e escrita restrita à própria pasta.
- SSH liberado apenas para o IP do operador.

---

## 7 · Custo

Dentro do nível gratuito: instância `t2.micro` por 750 h/mês no primeiro
ano, endereço fixo sem custo enquanto associado a instância ativa, e
tráfego de saída bem abaixo do limite mensal — a resposta a cada leitura
tem poucas centenas de bytes.

Fora do nível gratuito, uma `t3.micro` fica na ordem de poucos dólares por
mês.

Para conter custo, parar a instância fora dos períodos de uso. O endereço
fixo é preservado; o serviço volta sozinho no próximo início, porque está
habilitado no systemd.
