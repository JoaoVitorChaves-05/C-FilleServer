#include <sys/types.h>          /* See NOTES */
#include <sys/socket.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <pthread.h>
#include <signal.h>

#include "../include/file.h"

void *handle_client_file(void *args) {
        thread_client_t client = *(thread_client_t *)args;

        //recv
        int nr, ns, fd;
    	msg_request_t request;
	    msg_reply_t reply;

        nr = recv(client.c, &request, sizeof(msg_request_t), 0);
        if (nr != sizeof(msg_request_t)) {
            if (nr < 0) {
                perror("recv");
            } else {
                fprintf(stderr, "Requisicao incompleta\n");
            }
            /* envia erro na requisicao */
            reply.code = REQ_ERR;
            reply.err = errno;
            ns = send(client.c, &reply, sizeof(msg_reply_t), 0);
            if (ns < 0) {
                perror("send");
            }
            close(client.c);
            pthread_exit(NULL);
        }

        printf("client[%s:%d] request: %d %s \n",
                inet_ntoa(client.caddr.sin_addr),
                ntohs(client.caddr.sin_port),
                request.method,
                request.file_path);

	    if (request.method == FILE_GET) {
		    fd = open(request.file_path, O_RDONLY);
		    if (fd < 0){
			    perror("open");
			    reply.code = FILE_ERR;
			    reply.err = errno;
		        ns = send(client.c, &reply, sizeof(msg_reply_t), 0);
            } else {
                /* envia um ok */
                reply.code = FILE_200;
                reply.err = 0;
                ns = send(client.c, &reply, sizeof(msg_reply_t), 0);

                /* comeca a enviar o arq */
                char block[BLOCK_SIZE];
                int nb;
                do {
                    nb = read(fd, block, BLOCK_SIZE);
                    if (nb > 0) {
                        // pode ser que o cliente tenha fechado a conexao, nesse caso, como seguir? o retorno do send finaliza o while?
                        /* send pode enviar menos que nb (envio parcial): repete
                         * a partir de block + total ate mandar o bloco inteiro.
                         * MSG_NOSIGNAL: se o cliente ja fechou, o send retorna -1
                         * com EPIPE em vez de gerar SIGPIPE, que mataria o
                         * processo inteiro (todas as threads/clientes). */
                        int total = 0;
                        while (total < nb) {
                            ns = send(client.c, block + total, nb - total, MSG_NOSIGNAL);
                            if (ns <= 0) {
                                perror("send");     /* EPIPE/ECONNRESET: cliente fechou */
                                break;
                            }
                            total += ns;
                        }
                        if (total < nb) {
                            break;      /* cliente sumiu: aborta a transferencia */
                        }
                    }
                    else if (nb < 0) {
                        perror("read");
                        break;
                    }
                } while(nb > 0);

                /* Nao envia FILE_EOF: o cliente le ate recv() retornar 0, entao
                 * o struct de EOF seria gravado no arquivo como se fosse dado.
                 * O close(client.c) no fim da funcao ja sinaliza o fim do arquivo. */
                close(fd);
            }
	    }
        else if(request.method == FILE_PUT){
            fd = open(request.file_path, O_WRONLY | O_CREAT | O_TRUNC, 0666);
		    if (fd < 0){
			    perror("open");
			    reply.code = FILE_ERR;
			    reply.err = errno;
		        ns = send(client.c, &reply, sizeof(msg_reply_t), 0);
		    }
            else {
                reply.code = FILE_200;
                reply.err = 0;
                ns = send(client.c, &reply, sizeof(msg_reply_t), 0);
                if(ns < 0){
                    perror("send code 200");
                }
                char block[BLOCK_SIZE];
                int nb;
                while ((nb = recv(client.c, block, sizeof(block), 0)) > 0) {
                    int total = 0;
                    while (total < nb) {
                        int nw = write(fd, block + total, nb - total);

                        if (nw <= 0) {
                            perror("write");
                            break;
                        }
                        total += nw;
                    }
                    if (total < nb) {
                        break;
                    }
                }

                if (nb < 0) {
                    if (errno != EINTR) {
                        perror("recv");
                    }
                }
                reply.code = FILE_EOF;
                reply.err = 0;
                ns = send(client.c, &reply, sizeof(msg_reply_t), 0);
                if(ns < 0){
                    perror("send EOF");
                }
                close(fd);
            }
        }
        else{
            reply.code = REQ_ERR;
            reply.err = errno;
            ns = send(client.c, &reply, sizeof(msg_reply_t), 0);
            if (ns < 0) {
                perror("send REQ_ERR");
            }
        }
        close(client.c);
        pthread_exit(NULL);
}

int main (int argc, char **argv) {
	// ./server <port>
	if (argc != 2) {
		printf("Uso: %s <port>\n", argv[0]);
		return 0;
	}

	/* Ignora SIGPIPE no processo todo: escrever num socket que o cliente ja
	 * fechou gera SIGPIPE, cuja acao padrao eh TERMINAR o processo (todas as
	 * threads, nao so a do cliente). Ignorando, send() so retorna -1/EPIPE.
	 * Reforca o MSG_NOSIGNAL usado nos send do handle_client_file. */
	signal(SIGPIPE, SIG_IGN);

	//socket
	int s;
	s = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
	if (s < 0) {
		perror("socket");
		return -1;
	}

	struct sockaddr_in saddr;
	saddr.sin_family = AF_INET;
	saddr.sin_port = htons(atoi(argv[1]));
	saddr.sin_addr.s_addr = INADDR_ANY;
	
	//bind
	if (bind(s, (struct sockaddr *)&saddr, sizeof(struct sockaddr_in)) < 0) {
		perror("bind");
                return -1;
	}
	
	//listen
	if (listen(s, MAX_CONN) < 0) {
		perror("listen");
                return -1;
	}
	
	//accept
	thread_client_t clients[MAX_CONN];
	int i = 0;
	while (1) {
		clients[i].addrlen = sizeof(struct sockaddr_in);
		clients[i].c = accept(s,
				(struct sockaddr *)&clients[i].caddr,
				&clients[i].addrlen);
		if (clients[i].c < 0) {
			perror("accept");
	               return -1;
		}
		pthread_create(&clients[i].t, NULL, handle_client_file, &clients[i]);
		pthread_detach(clients[i].t);
		i = (i + 1) % MAX_CONN;
	}
	close(s);
	return 0;
}