
#!/bin/bash
# uso: ./put_paralelos.sh N arquivo repeticoes

N=${1:-10}
ARQ=${2:-pagina_web_teste.html}
REPETICOES=${3:-11}

SERVER=10.0.4.20
PORTA=5050
CLIENT=$HOME/projeto_sockets/client_Dir/client

[ -x "$CLIENT" ] || { echo "Cliente nao encontrado: $CLIENT"; exit 1; }
ulimit -n 4096 2>/dev/null

ORIGEM=$(readlink -f "$ARQ")

if [ ! -f "$ORIGEM" ]; then
    echo "Arquivo $ARQ nao encontrado"
    exit 1
fi

EXT="${ARQ##*.}"

RESULTADOS="resultados_put_N${N}_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTADOS"
CSV="$RESULTADOS/resultados.csv"
ERROS="$RESULTADOS/erros.txt"

echo "repeticao,cliente,status,metodo,bytes,rtt_ms,t_req_ms,t_dados_ms,vazao_req_mbps,vazao_dados_mbps" > "$CSV"
: > "$ERROS"

BASE=$(mktemp -d /tmp/puts.XXXXXX)
trap 'rm -rf "$BASE"' EXIT

FALHAS=0

echo "PUT | Clientes: $N | Arquivo: $ARQ | Repeticoes: $REPETICOES"

for REP in $(seq 1 "$REPETICOES"); do
    PIDS=()
    INI=$(date +%s.%N)

    for i in $(seq 1 "$N"); do
        (
            D="$BASE/c$i"
            mkdir -p "$D" && cd "$D" || exit 1

            # Nome unico por cliente/repeticao
            NOME="put_r${REP}_c${i}.${EXT}"

            ln -s "$ORIGEM" "$NOME" 2>/dev/null || cp "$ORIGEM" "$NOME"

            "$CLIENT" "$SERVER" "$PORTA" PUT "$NOME" \
                > "$D/out.txt" 2> "$D/err.txt"

            ST=$?
            exit $ST
        ) &
        PIDS+=("$!")
    done

    # espera cada cliente e guarda o status na ordem
    i=0
    for PID in "${PIDS[@]}"; do
        i=$((i+1))
        wait "$PID"
        ST=$?

        D="$BASE/c$i"

        if [ "$ST" -eq 0 ] && [ -s "$D/out.txt" ]; then
            echo "$REP,$i,0,$(head -n1 "$D/out.txt")" >> "$CSV"
        else
            FALHAS=$((FALHAS+1))
            echo "$REP,$i,1,PUT,0,0,0,0,0,0" >> "$CSV"
            echo "rep $REP cli $i (exit $ST): $(head -n1 "$D/err.txt")" >> "$ERROS"
        fi

        rm -rf "$D"
    done

    FIM=$(date +%s.%N)

    echo "Repeticao $REP/$REPETICOES: $(awk -v a="$INI" -v b="$FIM" 'BEGIN{printf "%.3f",b-a}') s"
done

echo "Falhas: $FALHAS (detalhes em $ERROS)"
echo "Resultados: $CSV"
