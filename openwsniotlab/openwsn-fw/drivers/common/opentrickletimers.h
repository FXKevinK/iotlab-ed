/**
\brief trickle timer

\author Dzaky Zakiyal Fawwaz <dzakybd@gmail.com>
*/

#ifndef __OPENTRICKLETIMERS_H
#define __OPENTRICKLETIMERS_H

#include "opendefs.h"
#include "opentimers.h"
#include "IEEE802154E.h"
#include "board.h"

/**
\addtogroup drivers
\{
\addtogroup OpenTrickleTimers
\{
*/

// RFC: 6206 <https://tools.ietf.org/html/rfc6206>

//=========================== define ==========================================

// DIO trickle timer parameters
#define DEFAULT_DIO_REDUNDANCY_CONSTANT 10
#define DEFAULT_DIO_INTERVAL_DOUBLINGS 8
#define MINIMAL_CELL_BUSY_RATIO_SLOTFRAME 10

// ignore ig
#define DEFAULT_DIO_INTERVAL_MIN 5000
// #define IMIN_1 (1 << DEFAULT_DIO_INTERVAL_MIN)

// milliseconds, DIO_IMIN = 2 ^ DEFAULT_DIO_INTERVAL_MIN
// #if PYTHON_BOARD
// #define IMIN_2 (DEFAULT_DIO_INTERVAL_MIN * 60)
// #else
#define IMIN_2 DEFAULT_DIO_INTERVAL_MIN
// #endif
#define DEFAULT_DIO_IMIN_MS IMIN_2

#if use_qtrickle == TRUE
#define ql_learning_rate 0.7
#define ql_discount_rate 0.2
#define default_epsilon 0.9
#endif

//=========================== typedef =========================================

// |-------+-----+------------------------------|
//         T I = Imin                max_interval (Imin*2^Imax)

//=========================== module variables ================================

BEGIN_PACK
typedef struct {
    uint8_t Nnbr;
    uint8_t K;
    int16_t reward;
    uint16_t state;
    uint16_t DIOtransmit;
    uint16_t DIOsuppress;
    uint16_t DIOfailed;
    uint16_t psent;
    uint16_t pbusy;
    uint16_t pqu;
    uint16_t preset;
    uint16_t ptransmit;
    uint32_t T;
} opentrickletimers_debug_t;
END_PACK

typedef struct
{
    uint32_t Imin;
    uint8_t Imax;
    uint64_t max_interval;
    uint8_t K;
    uint32_t I;
    opentimers_cbt callback;
    bool isUsed;
    bool isRunning;
    bool is_dio_sent;
    uint16_t Nstates;
    uint16_t Ncells;
    uint16_t DIOtransmit;
    uint16_t DIOfailed;
    uint16_t DIOsuppress;
    uint16_t used;
    uint8_t Nnbr;
    uint32_t T;
    uint8_t C;

    uint16_t Nreset;
    float pbusy;
    float preset;
    float pstable;
    float ptransmit;
    float pfailed;
    float psent;
    float pqu;
    float ops;
    float epsilon;

    uint8_t sc_at_i;
    uint8_t sc_at_t;
    uint8_t sc_at_start_t;
    uint8_t sc_at_end_t;
    uint32_t t_start;
    uint32_t t_end;
    float reward;

#if use_qtrickle == TRUE
    uint8_t current_action;
    float psent_prev;
    float pbusy_prev;
    float pqu_prev;

    bool is_explore;
    // skip 0 index, since 0 * 0 and 0 * 1 will be the same
    float ql_table[3][3][2];
    uint8_t s1;
    uint8_t s2;
    uint8_t n_s1;
    uint8_t n_s2;
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
uint32_t opentrickletimers_get_p(uint8_t code);
uint8_t opentrickletimers_prob_to_class(float prob);
bool opentrickletimers_isInTRange(void);

/**
\}
\}
*/

#endif