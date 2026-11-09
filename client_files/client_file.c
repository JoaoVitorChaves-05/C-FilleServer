#include "../include/file.h"
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/time.h>

/* Tempo decorrido entre t1 e t2, em segundos.
 * struct timeval tem duas partes: tv_sec (segundos) e tv_usec (microssegundos,
 * de 0 a 999999). Quando t2.tv_usec < t1.tv_usec a parte de usec fica negativa,
 * mas a diferenca em tv_sec compensa: 2.1s - 1.9s = (2-1) + (100000-900000)/1e6 = 0.2s */
static double elapsed_s(struct timeval t1, struct timeval t2) {
	return (t2.tv_sec - t1.tv_sec) + (t2.tv_usec - t1.tv_usec) / 1e6;
}

int main (int argc, char *argv[]) {
	// ./client <server ip> <server port> <method> <file path>
	if (argc != 5) {
		printf("Uso: %s <server ip> <server port> <method> <file path>\n", argv[0]);
		return -1;
	}
	
	struct msg_request_t request;
	struct msg_reply_t reply;

	/* build request msg */
	strncpy(request.file_path, argv[4], PATH_LEN - 1);
	request.file_path[PATH_LEN - 1] = '\0';

	// GET || PUT
	if (strcmp(argv[3], "GET") == 0) request.method = FILE_GET;
	else if (strcmp(argv[3], "PUT") == 0) request.method = FILE_PUT;
	else  {
		printf("%s: metodo invalido, use GET ou PUT\n", argv[3]);
		return -1;
	}
	/* end build request msg */

	// socket
	int sfd;
	sfd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
	if (sfd < 0) {
		perror("socket");
		return -1;
	}

	// socket address
	struct sockaddr_in saddr;
	saddr.sin_family = AF_INET;
	saddr.sin_port = htons(atoi(argv[2]));
	saddr.sin_addr.s_addr = inet_addr(argv[1]);

	/* ---- metricas ---- */
	struct timeval t1_conn, t2_conn;				/* connect: 1 RTT */
	struct timeval t1_req, t2_req;					/* requisicao inteira: do connect ate o fim da resposta */
	struct timeval t1_dados = {0}, t2_dados = {0};	/* so a transferencia do arquivo */
	long long bytes = 0;							/* bytes do arquivo transferidos (GET ou PUT) */

	// connect
	/* O connect() de um socket TCP bloqueia ate o handshake: o cliente manda SYN
	 * e o connect retorna quando chega o SYN/ACK. Ida e volta = 1 RTT. */
	gettimeofday(&t1_conn, NULL);
	if (connect(sfd, (struct sockaddr *)&saddr, sizeof(struct sockaddr_in)) < 0) {
		perror("connect");
		return -1;
	}
	gettimeofday(&t2_conn, NULL);

	/* t1_requisicao: do connect ate a resposta do servidor, entao ela comeca junto com o connect. */
	t1_req = t1_conn;

	/* ---- GET ---- */
	if (request.method == FILE_GET) {
		// send
		int ns = send(sfd, &request, sizeof(struct msg_request_t), 0);
		if (ns != sizeof(struct msg_request_t)) { 
			if (ns < 0) {
				perror("send");
			}
			else {
				fprintf(stderr, "Envio incompleto\n");
			}
			close(sfd);
			return -1;
		}
		// recv
		/* MSG_WAITALL: garante o struct inteiro */
		int nr = recv(sfd, &reply, sizeof(struct msg_reply_t), MSG_WAITALL);

		/* Inicia a contagem do tempo de transferencia dos dados 
		 * (do momento em que o servidor respondeu com FILE_200 ate o fim da transferencia) */
		gettimeofday(&t1_dados, NULL);

		if (nr != sizeof(struct msg_reply_t)) {
			if (nr < 0) {
				perror("recv");
			}
			else {
				fprintf(stderr, "Resposta incompleta do servidor\n");
			}
			close(sfd);
			return -1;
		}

		if		(reply.code == REQ_ERR) {
			fprintf(stderr, "Erro de requisicao: %s\n", strerror(reply.err));
			close(sfd);
			return -1;
		}
		else if (reply.code == FILE_ERR) {
			fprintf(stderr, "Erro de arquivo: %s\n", strerror(reply.err));
			close(sfd);
			return -1;
		}
		else if (reply.code == FILE_200)  {
			int fd = open(request.file_path, O_WRONLY | O_CREAT | O_TRUNC, 0666);
			if (fd < 0) {
				perror("open");
				close(sfd);
				return -1;
			}

			/* inicio da transferencia: o servidor ja respondeu FILE_200 e os
			 * proximos bytes no socket sao o conteudo do arquivo */
			do {
				char block[BLOCK_SIZE];
				nr = recv(sfd, block, sizeof(block), 0);
				if (nr > 0) {
					int total = 0;
					/* envia o bloco para o arquivo */
					while (total < nr) {
						int nw = write(fd, block + total, nr - total);
						if (nw <= 0) {
							perror("write");
							break;
						}
						total += nw;
					}
					bytes += total;		/* atualiza o número de bytes escritos */
					if (total < nr) { 	/* bloco nao foi totalmente escrito */
						close(fd);
						close(sfd);
						return -1;		/* erro ao escrever o bloco: fecha a conexao */
					}
				}
				else if (nr < 0) {
					perror("recv");
					close(fd);
					close(sfd);
					return -1;			/* erro ao receber o bloco: fecha a conexao */
				}
			} while (nr > 0); /* nr == 0: o servidor fechou a conexao */
			/* fim da transferencia: recv retornou 0, o arquivo chegou inteiro */
			gettimeofday(&t2_dados, NULL);

			close(fd);
		}
		close(sfd);
	}

	/* ---- PUT ---- */
	else if (request.method == FILE_PUT) {
		int fd = open(request.file_path, O_RDONLY);
		if (fd < 0) {
			perror("open");
			close(sfd);
			return -1;
		}
		
		// send
		int ns = send(sfd, &request, sizeof(struct msg_request_t), 0);
		if (ns != sizeof(struct msg_request_t)) { 
			if (ns < 0) {
				perror("send");
			}
			else {
				fprintf(stderr, "Envio incompleto\n");
			}
			close(fd);
			close(sfd);
			return -1;
		}

		// recv
		/* MSG_WAITALL: garante o struct inteiro (ver comentario no GET) */
		int nr = recv(sfd, &reply, sizeof(struct msg_reply_t), MSG_WAITALL);
		if (nr != sizeof(struct msg_reply_t)) {
			if (nr < 0) {
				perror("recv");
			}
			else {
				fprintf(stderr, "Resposta incompleta do servidor\n");
			}
			close(fd);
			close(sfd);
			return -1;
		}

		if		(reply.code == REQ_ERR) {
			fprintf(stderr, "Erro de requisicao: %s\n", strerror(reply.err));
			close(fd);
			close(sfd);
			return -1;
		}
		else if (reply.code == FILE_ERR) {
			fprintf(stderr, "Erro de arquivo: %s\n", strerror(reply.err));
			close(fd);
			close(sfd);
			return -1;
		}
		else if (reply.code == FILE_200)  {
			/* inicio da transferencia: o servidor ja respondeu FILE_200 e os
			 * proximos bytes no socket sao o conteudo do arquivo */
			gettimeofday(&t1_dados, NULL);
			char block[BLOCK_SIZE];
			int nb;
			while ((nb = read(fd, block, sizeof(block))) > 0) {
				int total = 0;
				while (total < nb) {
					/* MSG_NOSIGNAL: se o servidor fechar no meio, o send retorna
					 * -1/EPIPE em vez de o processo morrer por SIGPIPE sem imprimir nada */
					ns = send(sfd, block + total, nb - total, MSG_NOSIGNAL);
					if (ns <= 0) {
						perror("send");
						break;
					}
					total += ns;
				}
				bytes += total; /* atualiza o número de bytes enviados */
				if (total < nb) { /* bloco nao foi totalmente enviado */
					close(fd);
					close(sfd);
					return -1; /* erro ao enviar o bloco: fecha a conexao */
				}
			}
			if (nb < 0) {
				perror("read");
				close(fd);
				close(sfd);
				return -1; /* erro ao ler o bloco: fecha a conexao */
			}
			close(fd);

			/* Envia um FIN para o servidor, indicando que nao vamos enviar mais dados */
			if (shutdown(sfd, SHUT_WR) < 0) {
				perror("shutdown");
				close(sfd);
				return -1;
			}

			nr = recv(sfd, &reply, sizeof(struct msg_reply_t), MSG_WAITALL);
			/* fim da transferencia: o servidor confirmou que recebeu tudo */
			gettimeofday(&t2_dados, NULL);

			if (nr != sizeof(struct msg_reply_t)) {
				if (nr < 0) {
					perror("recv");
				}
				else {
					fprintf(stderr, "Servidor nao confirmou o PUT\n");
				}
				close(sfd);
				return -1;
			}
			if (reply.code != FILE_EOF) {
				/* ex.: disco cheio no servidor (write falhou) */
				fprintf(stderr, "Erro de arquivo no servidor: %s\n", strerror(reply.err));
				close(sfd);
				return -1;
			}
		}
		close(sfd);
	}

	/* t2_requisicao: fim da requisicao inteira (arquivo transferido) */
	gettimeofday(&t2_req, NULL);

	/* ---- calculo das metricas ---- */
	double rtt     = elapsed_s(t1_conn, t2_conn);	/* 1 RTT, em segundos */
	double t_req   = elapsed_s(t1_req, t2_req);		/* requisicao inteira, em segundos */
	double t_dados = elapsed_s(t1_dados, t2_dados);	/* transferencia do arquivo, em segundos */

	/* Vazao = quantidade / tempo
	 * bytes * 8 converte para bits, / 1e6 para mega: resultado em Mbps.
	 * O '> 0' evita divisao por zero (ex.: PUT ainda vazio, t_dados = 0). */
	double vazao_req   = t_req   > 0 ? (bytes * 8.0) / t_req   / 1e6 : 0;
	double vazao_dados = t_dados > 0 ? (bytes * 8.0) / t_dados / 1e6 : 0;

	/* RTT medio: cada execucao mede 1 RTT no connect. O "medio" do testes.md
	 * sai da media dessa coluna entre todas as requisicoes/execucoes, feita
	 * pelo script de teste ao juntar as linhas abaixo. */

	/* Uma linha CSV por requisicao no stdout (erros vao pro stderr e nao
	 * misturam). Colunas:
	 * metodo,bytes,rtt_ms,t_req_ms,t_dados_ms,vazao_req_mbps,vazao_dados_mbps */
	printf("%s,%lld,%.3f,%.3f,%.3f,%.3f,%.3f\n",
			argv[3], bytes,
			rtt * 1e3, t_req * 1e3, t_dados * 1e3,
			vazao_req, vazao_dados);

	return 0;
}