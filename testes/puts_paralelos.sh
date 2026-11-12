#!/bin/bash
# uso: ./put_paralelo.sh N arquivo_origem repeticoes
N=${1:-10}
ARQ=${2:-pagina_web_teste.html}
REPETICOES=${3:-11}

SERVER=10.0.4.20
PORTA=5050
CLIENT=$HOME/projeto_sockets/client
ORIGEM=$(readlink -f "$ARQ")      # caminho absoluto do arquivo a enviar

if [ ! -f "$ORIGEM" ]; then
    echo "Arquivo $ARQ nao encontrado"; exit 1
fi

TAMANHO=$(stat -c%s "$ORIGEM")
EXT="${ARQ##*.}"

RESULTADOS="resultados_put_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTADOS"
CSV="$RESULTADOS/resultados.csv"
echo "repeticao,cliente,tempo_s,tamanho_bytes,vazao_mbps,status" > "$CSV"

FALHAS=0
echo "Iniciando testes PUT"
echo "Clientes: $N | Arquivo: $ARQ ($TAMANHO bytes) | Repeticoes: $REPETICOES"

for REP in $(seq 1 "$REPETICOES"); do
    echo "Repeticao $REP/$REPETICOES"
    PIDS=()
    METRICAS=$(mktemp -d)
    INICIO_TOTAL=$(date +%s%N)

    for i in $(seq 1 "$N"); do
        (
            DIR=$(mktemp -d)
            cd "$DIR" || exit 1

            # nome unico por cliente/repeticao, para nao colidir no servidor
            NOME="put_r${REP}_c${i}.${EXT}"
            ln -s "$ORIGEM" "$NOME" 2>/dev/null || cp "$ORIGEM" "$NOME"

            INICIO=$(date +%s%N)
            "$CLIENT" "$SERVER" "$PORTA" PUT "$NOME" \
                > "$METRICAS/saida_${i}.txt" 2>&1
            STATUS=$?
            FIM=$(date +%s%N)

            if [ "$STATUS" -ne 0 ]; then
                BYTES=0
            else
                BYTES=$TAMANHO
            fi

            awk -v r="$REP" -v c="$i" -v ini="$INICIO" -v fim="$FIM" \
                -v b="$BYTES" -v s="$STATUS" 'BEGIN {
                    t=(fim-ini)/1e9;
                    v=(t>0)?(b*8)/(t*1e6):0;
                    printf "%s,%s,%.6f,%s,%.3f,%s\n", r,c,t,b,v,s
                }' > "$METRICAS/cliente_${i}.csv"

            cd /
            rm -rf "$DIR"
            exit "$STATUS"
        ) &
        PIDS+=("$!")
    done

    for PID in "${PIDS[@]}"; do
        wait "$PID" || FALHAS=$((FALHAS+1))
    done

    FIM_TOTAL=$(date +%s%N)
    TEMPO_TOTAL=$(awk -v ini="$INICIO_TOTAL" -v fim="$FIM_TOTAL" \
        'BEGIN { printf "%.6f", (fim-ini)/1e9 }')

    cat "$METRICAS"/cliente_*.csv >> "$CSV"
    rm -rf "$METRICAS"
    echo "Tempo total: $TEMPO_TOTAL s"
done

echo "Testes finalizados. Falhas: $FALHAS"
echo "Resultados: $CSV"