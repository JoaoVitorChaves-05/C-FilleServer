# Tipos de arquivo
- MP4
- PDF

# Requisicoes
- P processos de cliente rodando no noh
- 50 requisicoes por cliente
- sendo metade requisicoes GET e metade requisicoes PUT
- e a mesma abordagem para os tipos de arquivo

# Tecnologias
- duas tecnologias: 4G e Fibra Otica
- um teste por tecnologia

# Testes
- Cenario 1: 5 processos clientes, tecnologia 4G
- Cenario 2: 10 processos clientes, tecnologia 4G
- Cenario 3: 50 processos clientes, tecnologia 4G

- Cenario 4: 5 processos clientes, tecnologia Fibra Otica
- Cenario 5: 10 processos clientes, tecnologia Fibra Otica
- Cenario 6: 50 processos clientes, tecnologia Fibra Otica

- n > 10 execucoes por teste

- todos rodando 50 requisicoes com metodo escolhido aleatoriamente
```sh
./exec_teste <P processos> <R requisicoes por processo> <tipo arquivo> <metodo: aleatorio (50-50), GET ou PUT>
```
# Metricas
- RTT e vazao
- RTT medio medido no codigo
- Uma medida para o connect (1 RTT)
- Uma medida para a requisicao inteira (connect ate a resposta do servidor)
- Uma medida para o tempo de transferencia do arquivo
- Calculo da vazao para o tempo total da requisicao e para o tempo de transferecnia de arquivo

#Fibra
time=5.49 ms
400 Mbps downstream
200 Mbps upstream

#4G
time=20.0 ms
45 Mbps downstream
22 Mbps upstream

