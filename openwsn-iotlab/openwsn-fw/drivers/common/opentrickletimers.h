/**
\brief trickle timer

\author Dzaky Zakiyal Fawwaz <dzakybd@gmail.com>
*/

#ifndef __OPENTRICKLETIMERS_H
#define __OPENTRICKLETIMERS_H

#include "opendefs.h"
#include "opentimers.h"
#include "board.h"

/**
\addtogroup drivers
\{
\addtogroup OpenTrickleTimers
\{
*/

// RFC: 6206 <https://tools.ietf.org/html/rfc6206>

//=========================== define ==========================================

#define use_qtrickle TRUE
#define adaptive_epsilon TRUE

// DIO trickle timer parameters
#define DEFAULT_DIO_INTERVAL_MIN 12
#define DEFAULT_DIO_REDUNDANCY_CONSTANT 10
#define DEFAULT_DIO_INTERVAL_DOUBLINGS 8
#define MINIMAL_CELL_BUSY_RATIO_SLOTFRAME 10

#define IMIN_1 (1 << DEFAULT_DIO_INTERVAL_MIN)
// milliseconds, DIO_IMIN = 2 ^ DEFAULT_DIO_INTERVAL_MIN
#if PYTHON_BOARD
#define IMIN_2 (IMIN_1 * 60)
#else
#define IMIN_2 IMIN_1
#endif
#define DEFAULT_DIO_IMIN_MS IMIN_2

#if use_qtrickle == TRUE
#define ql_learning_rate 0.5
#define ql_discount_rate 0.2
#define default_epsilon 0.5
#endif

#if adaptive_epsilon == TRUE
#define max_epsilon 1.0
#define min_epsilon 0.01
#define decay_rate 0.2
#define epsilon_delta ((max_epsilon - min_epsilon) * decay_rate)
#endif

//=========================== typedef =========================================

// |-------+-----+------------------------------|
//         T I = Imin                max_interval (Imin*2^Imax)

//=========================== module variables ================================

BEGIN_PACK
typedef struct {
    uint8_t m;
    uint8_t Nnbr;
    uint8_t k;
    uint8_t counter;
    uint16_t state;
    uint16_t Nreset;
    uint16_t DIOtransmit;
    uint16_t DIOsurpress;
    uint16_t DIOtransmit_collision;
    uint16_t DIOtransmit_dis;
    uint16_t pfree; // in xxxx int
    uint16_t preset; // in xxxx int
    uint16_t t_pos; // in xxxx int
    uint16_t epsilon; // in xxxx int
    // int16_t poccupancy; // from 1 - pfree
    // uint16_t pstable; // from 1 - preset
    // size 4+(2*9) = 22
} opentrickletimers_debug_t;
END_PACK

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
    uint16_t DIOtransmit_dis;
    uint64_t max_interval;
    bool is_dio_sent;
    uint8_t sc_at_i;
    uint8_t sc_at_t;
    uint8_t sc_at_start_t;
    uint8_t sc_at_end_t;
    uint8_t sc_ambr;
    uint32_t t_min; // t_start
    uint32_t t_max; // t_end

    uint16_t DIOtransmit_collision;
    uint8_t Nnbr;
    float epsilon;

    uint16_t prev_ops_ambr;
    uint32_t counter_ambr;
    float ambr;

#if use_qtrickle == TRUE
    bool is_explore;
    uint8_t current_action;
    float ptransmit;
    float ptransmit_collision;
    // skip 0 index, since 0 * 0 and 0 * 1 will be the same
    float q_table[(DEFAULT_DIO_INTERVAL_DOUBLINGS + 1) * 2];
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
uint16_t opentrickletimers_getAMBR(void);
void opentrickletimers_incrementDioTransmitDis(void);

/**
\}
\}
*/

#endif