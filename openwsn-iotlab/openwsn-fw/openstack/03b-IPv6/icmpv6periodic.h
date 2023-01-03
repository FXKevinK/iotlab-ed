#ifndef OPENWSN_ICMPv6PERIODIC_H
#define OPENWSN_ICMPv6PERIODIC_H

#include "config.h"

#define app_pkPeriodSec 1
#define app_pkPeriodVar 0.1
#define app_pkLength 90

typedef struct
{
    uint16_t counter;
    uint16_t mote_id;
    uint32_t mote_duration;
} icmpv6periodic_info_t;

typedef struct
{
    bool busySending;
    opentimers_id_t timer_id;
    uint32_t min_duration;
    uint32_t max_duration;
    icmpv6periodic_info_t info;
} icmpv6periodic_vars_t;

void icmpv6periodic_init(void);
void icmpv6periodic_sendDone(OpenQueueEntry_t *msg, owerror_t error);

#endif