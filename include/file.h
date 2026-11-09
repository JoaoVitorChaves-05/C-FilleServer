#ifndef FILE_H
#define FILE_H

#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <pthread.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <unistd.h>
#include <errno.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <string.h>

#define MAX_REQ_LEN 256
#define MAX_RESP_LEN 2*MAX_REQ_LEN
#define MAX_CONN 10000

#define FILE_GET 0
#define FILE_PUT 1
#define FILE_EOF 2
#define FILE_ERR 3
#define REQ_ERR 4
#define FILE_200 200

#define PATH_LEN 256
#define BLOCK_SIZE 4096


struct msg_request_t{
	char method;
	char file_path[PATH_LEN];
};
typedef struct msg_request_t msg_request_t;

struct msg_reply_t{
	int code;
	int err;
};
typedef struct msg_reply_t msg_reply_t;

struct thread_client_t {
        int c;
        pthread_t t;
        socklen_t addrlen;
        struct sockaddr_in caddr;
};
typedef struct thread_client_t thread_client_t;

#endif