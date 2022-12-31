/**
\brief trickle timer

\author Jeongbae Park <wjdqo94@gmail.com>
*/

#ifndef __OPENTRICKLETIMERS_H
#define __OPENTRICKLETIMERS_H

#include "opendefs.h"
#include "opentimers.h"

/**
\addtogroup drivers
\{
\addtogroup OpenTrickleTimers
\{
*/

// RFC: 6206 <https://tools.ietf.org/html/rfc6206>

//=========================== define ==========================================

#define use_qtrickle FALSE
#define adaptive_epsilon FALSE

// DIO trickle timer parameters
#define DEFAULT_DIO_INTERVAL_MIN_SMALL 14
#define DEFAULT_DIO_INTERVAL_DOUBLINGS_SMALL 3
#define DEFAULT_DIO_REDUNDANCY_CONSTANT 10
#define DEFAULT_DIO_INTERVAL_DOUBLINGS_LARGE (1 << DEFAULT_DIO_INTERVAL_DOUBLINGS_SMALL)

#define DEFAULT_DIO_INTERVAL_DOUBLINGS DEFAULT_DIO_INTERVAL_DOUBLINGS_SMALL
#define DEFAULT_DIO_IMAX DEFAULT_DIO_INTERVAL_DOUBLINGS_LARGE
#define DEFAULT_DIO_INTERVAL_MIN DEFAULT_DIO_INTERVAL_MIN_SMALL
#define DEFAULT_DIO_IMIN_MS (1 << DEFAULT_DIO_INTERVAL_MIN) // milliseconds, DIO_IMIN = 2 ^ DEFAULT_DIO_INTERVAL_MIN

#if use_qtrickle == TRUE
#define ql_learning_rate 0.05
#define ql_discount_rate 0.99
#define default_epsilon 0.5
#endif

#if adaptive_epsilon == TRUE
#define max_epsilon 1.0
#define min_epsilon 0.01
#define decay_rate 0.1
#define epsilon_delta ((max_epsilon - min_epsilon) * decay_rate)
#endif

//=========================== typedef =========================================

// |-------+-----+------------------------------|
//         T I = Imin                max_interval (Imin*2^Imax)

//=========================== module variables ================================

typedef struct
{
    uint32_t Imin;
    uint8_t Imax;
    uint8_t K;
    uint32_t I;
    uint32_t T;
    uint8_t C;
    opentimers_cbt callback;
    bool isUsed;
    bool isRunning;
    uint8_t m;
    uint16_t Nreset;
    uint16_t Nstates;
    float preset;
    float pstable;
    float pfree;
    float poccupancy;
    float t_pos;
    uint16_t Ncells;
    uint16_t start_ops;
    uint16_t end_ops;
    uint16_t DIOtransmit;
    uint16_t DIOsurpress;
    uint64_t max_interval;
    bool is_dio_sent;
    uint8_t sc_at_i;
    uint8_t sc_at_t;
    uint8_t sc_at_start_t;
    uint8_t sc_at_end_t;
    uint32_t t_min; // t_start
    uint32_t t_max; // t_end

#if use_qtrickle == TRUE
    bool is_explore;
    uint8_t current_action;
    uint8_t Nnbr;
    uint16_t DIOtransmit_collision;
    float epsilon;
    float ptransmit;
    float ptransmit_collision;
    // skip 0 index, since 0 * 0 and 0 * 1 will be the same
    float q_table[(DEFAULT_DIO_IMAX + 1) * 2];
#endif

#if adaptive_epsilon == TRUE
    float total_reward;
    float prev_total_reward;
#endif

} opentrickletimers_vars_t;

//=========================== prototypes ======================================

void opentrickletimers_init(void);
opentimers_id_t opentrickletimers_create(uint8_t timer_id, uint8_t task_prio);
bool opentrickletimers_initialize(opentimers_id_t id, opentimers_cbt cb);
void opentrickletimers_start(opentimers_id_t id);
bool opentrickletimers_stop(opentimers_id_t id);
bool opentrickletimers_recvConsistent(opentimers_id_t id);
bool opentrickletimers_reset(opentimers_id_t id);
uint32_t opentrickletimers_getValue(uint8_t code);

/**
\}
\}
*/

#endif