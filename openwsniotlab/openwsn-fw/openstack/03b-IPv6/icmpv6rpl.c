#include "opendefs.h"
#include "icmpv6rpl.h"
#include "icmpv6.h"
#include "openserial.h"
#include "openqueue.h"
#include "neighbors.h"
#include "packetfunctions.h"
#include "openrandom.h"
#include "scheduler.h"
#include "idmanager.h"
#include "opentimers.h"
#include "opentrickletimers.h"
#include "IEEE802154E.h"
#include "IEEE802154_security.h"
#include "schedule.h"
#include "msf.h"
#include "icmpv6periodic.h"

//=========================== definition ======================================
#if RPL_DIS_TRANSMISSION == TRUE
#define DIS_PORTION 40
#endif

//=========================== variables =======================================

icmpv6rpl_vars_t icmpv6rpl_vars;
icmpv6rpl_debug_t icmpv6rpl_debug;

//=========================== prototypes ======================================

#if RPL_DIS_TRANSMISSION == TRUE
// DIS-related
void icmpv6rpl_timer_DIS_cb(opentimers_id_t id);
void icmpv6rpl_timer_DIS_task(void);
void sendDIS(void);
#endif // RPL_DIS_TRANSMISSION == TRUE

// DIO-related
void icmpv6rpl_timer_DIO_cb(opentimers_id_t id);
owerror_t sendDIO(bool is_trickle, bool is_priority);
// DAO-related
void icmpv6rpl_timer_DAO_cb(opentimers_id_t id);
void icmpv6rpl_timer_DAO_task(void);
void icmpv6rpl_dao_scheduleTimer(uint32_t duration);
void icmpv6rpl_dao_calculateRetransmissionTime(void);
owerror_t sendDAO(void);

//=========================== public ==========================================

/**
\brief Initialize this module.
*/
void icmpv6rpl_init(void)
{

    uint8_t dodagid[16];

    // retrieve my prefix and EUI64
    memcpy(&dodagid[0], idmanager_getMyID(ADDR_PREFIX)->prefix, 8); // prefix
    memcpy(&dodagid[8], idmanager_getMyID(ADDR_64B)->addr_64b, 8);  // eui64

    //===== reset local variables
    memset(&icmpv6rpl_vars, 0, sizeof(icmpv6rpl_vars_t));

    //=== routing
    icmpv6rpl_vars.haveParent = FALSE;
    icmpv6rpl_vars.ParentIndex = -1;
    icmpv6rpl_vars.daoSent = FALSE;

    icmpv6rpl_vars.count_dis = 0;
    icmpv6rpl_vars.count_dio = 0;
    icmpv6rpl_vars.count_dio_done = 0;
    icmpv6rpl_vars.count_dao = 0;
    icmpv6rpl_vars.count_dio_trickle = 0;
    icmpv6rpl_vars.count_dio_trickle_done = 0;
    

    if (idmanager_getIsDAGroot() == TRUE)
    {
        icmpv6rpl_vars.myDAGrank = MINHOPRANKINCREASE;
        icmpv6rpl_vars.lowestRankInHistory = MINHOPRANKINCREASE;
    }
    else
    {
        icmpv6rpl_vars.myDAGrank = DEFAULTDAGRANK;
        icmpv6rpl_vars.lowestRankInHistory = MAXDAGRANK;
    }

//=== admin
#if RPL_DIS_TRANSMISSION == TRUE
    icmpv6rpl_vars.busySendingDIS = FALSE;
    icmpv6rpl_vars.creatingDIS = FALSE;
#endif
    icmpv6rpl_vars.busySendingDIO = FALSE;
    icmpv6rpl_vars.busySendingDAO = FALSE;
    icmpv6rpl_vars.fDodagidWritten = 0;

#if RPL_DIS_TRANSMISSION == TRUE
    //=== DIS
    icmpv6rpl_vars.dis.flags = 0x00;
    icmpv6rpl_vars.dis.reserved = 0x00;

    icmpv6rpl_vars.disDestination.type = ADDR_128B;
    memcpy(&icmpv6rpl_vars.disDestination.addr_128b[0], all_rpl_nodes_multicast_lls, sizeof(all_rpl_nodes_multicast_lls));

    icmpv6rpl_vars.timerIdDIS = opentimers_create(TIMER_GENERAL_PURPOSE, TASKPRIO_RPL);

    if (idmanager_getIsDAGroot() == FALSE)
    {
        opentimers_scheduleIn(
            icmpv6rpl_vars.timerIdDIS,
            1000,
            TIME_MS,
            TIMER_PERIODIC,
            icmpv6rpl_timer_DIS_cb);
    }
#endif

    //=== DIO

    icmpv6rpl_vars.dio.rplinstanceId = DEFAULT_RPL_RPLINSTANCEID; ///< will be replaced upon receiving DIO
    icmpv6rpl_vars.dio.verNumb = DEFAULT_RPL_VERSIONNUMBER;       ///< will be replaced upon receiving DIO
    // rank: to be populated upon TX
    icmpv6rpl_vars.dio.rplOptions = MOP_DIO_A |
                                    MOP_DIO_B |
                                    MOP_DIO_C |
                                    PRF_DIO_A |
                                    PRF_DIO_B |
                                    PRF_DIO_C |
                                    G_DIO;
    icmpv6rpl_vars.dio.DTSN = DEFAULT_RPL_DTSN; ///< will be replaced upon receiving DIO
    icmpv6rpl_vars.dio.flags = 0x00;
    icmpv6rpl_vars.dio.reserved = 0x00;
    memcpy(
        &(icmpv6rpl_vars.dio.DODAGID[0]),
        dodagid,
        sizeof(icmpv6rpl_vars.dio.DODAGID)); // can be replaced later

    icmpv6rpl_vars.dioDestination.type = ADDR_128B;
    memcpy(&icmpv6rpl_vars.dioDestination.addr_128b[0], all_rpl_nodes_multicast_lls, sizeof(all_rpl_nodes_multicast_lls));

    icmpv6rpl_vars.timerIdDIO = opentrickletimers_create(TIMER_GENERAL_PURPOSE, TASKPRIO_RPL);

    // initialize PIO -> move this to dagroot code
    icmpv6rpl_vars.pio.type = RPL_OPTION_PIO;
    icmpv6rpl_vars.pio.optLen = 30;
    icmpv6rpl_vars.pio.prefLen = 64;
    icmpv6rpl_vars.pio.flags = 0x20;
    icmpv6rpl_vars.pio.plifetime = 0xFFFFFFFF;
    icmpv6rpl_vars.pio.vlifetime = 0xFFFFFFFF;
    // if not dagroot then do not initialize, will receive PIO and update fields
    // later
    if (idmanager_getIsDAGroot())
    {
        memcpy(
            &(icmpv6rpl_vars.pio.prefix[0]),
            idmanager_getMyID(ADDR_PREFIX)->prefix,
            sizeof(idmanager_getMyID(ADDR_PREFIX)->prefix));
        memcpy(
            &(icmpv6rpl_vars.pio.prefix[8]),
            idmanager_getMyID(ADDR_64B)->addr_64b,
            sizeof(idmanager_getMyID(ADDR_64B)->addr_64b));
    }
    // configuration option
    icmpv6rpl_vars.conf.type = RPL_OPTION_CONFIG;
    icmpv6rpl_vars.conf.optLen = 14;
    icmpv6rpl_vars.conf.flagsAPCS = DEFAULT_PATH_CONTROL_SIZE;
    icmpv6rpl_vars.conf.DIOIntDoubl = DEFAULT_DIO_INTERVAL_DOUBLINGS;
    icmpv6rpl_vars.conf.DIOIntMin = 12;
    icmpv6rpl_vars.conf.DIORedun = DEFAULT_DIO_REDUNDANCY_CONSTANT;
    icmpv6rpl_vars.conf.maxRankIncrease = DEFAULT_RPL_MAXRANKINCREASE;
    icmpv6rpl_vars.conf.minHopRankIncrease = DEFAULT_RPL_MINHOPRANKINCREASE;
    icmpv6rpl_vars.conf.OCP = DEFAULT_RPL_OCP; // MRHOF
    icmpv6rpl_vars.conf.reserved = 0;
    icmpv6rpl_vars.conf.defLifetime = DEFAULT_RPL_DEFAULTLIFETIME;
    icmpv6rpl_vars.conf.lifetimeUnit = DEFAULT_RPL_LIFETIMEUNIT;

    opentrickletimers_initialize(icmpv6rpl_vars.timerIdDIO, icmpv6rpl_timer_DIO_cb);

    if (idmanager_getIsDAGroot() == TRUE)
    {
        icmpv6rpl_start_or_reset_trickle_timer();
    }

    //=== DAO

    icmpv6rpl_vars.dao.rplinstanceId = 0x00; ///< will be replaced upon receiving DIO
    icmpv6rpl_vars.dao.K_D_flags = FLAG_DAO_A |
                                   FLAG_DAO_B |
                                   FLAG_DAO_C |
                                   FLAG_DAO_D |
                                   FLAG_DAO_E |
                                   PRF_DIO_C |
                                   FLAG_DAO_F |
                                   D_DAO |
                                   K_DAO;
    icmpv6rpl_vars.dao.reserved = 0x00;
    icmpv6rpl_vars.dao.DAOSequence = 0x00;
    memcpy(
        &(icmpv6rpl_vars.dao.DODAGID[0]),
        dodagid,
        sizeof(icmpv6rpl_vars.dao.DODAGID)); // can be replaced later

    icmpv6rpl_vars.dao_transit.type = OPTION_TRANSIT_INFORMATION_TYPE;
    // optionLength: to be populated upon TX
    icmpv6rpl_vars.dao_transit.E_flags = E_DAO_Transit_Info;
    icmpv6rpl_vars.dao_transit.PathControl = PC1_A_DAO_Transit_Info |
                                             PC1_B_DAO_Transit_Info |
                                             PC2_A_DAO_Transit_Info |
                                             PC2_B_DAO_Transit_Info |
                                             PC3_A_DAO_Transit_Info |
                                             PC3_B_DAO_Transit_Info |
                                             PC4_A_DAO_Transit_Info |
                                             PC4_B_DAO_Transit_Info;
    icmpv6rpl_vars.dao_transit.PathSequence = 0x00; // to be incremented at each TX
    icmpv6rpl_vars.dao_transit.PathLifetime = 0xAA;
    // target information
    icmpv6rpl_vars.dao_target.type = OPTION_TARGET_INFORMATION_TYPE;
    icmpv6rpl_vars.dao_target.optionLength = 0;
    icmpv6rpl_vars.dao_target.flags = 0;
    icmpv6rpl_vars.dao_target.prefixLength = 0;

    icmpv6rpl_vars.timerIdDAO = opentimers_create(TIMER_GENERAL_PURPOSE, TASKPRIO_RPL);
    icmpv6rpl_vars.dao_numFail = 0;
    icmpv6rpl_dao_calculateRetransmissionTime();
    icmpv6rpl_dao_scheduleTimer(icmpv6rpl_vars.dao_retransmissionTime);
}

void icmpv6rpl_start_or_reset_trickle_timer(void)
{
    if (icmpv6rpl_vars.timerIdDIO < 0 || MAX_NUM_TIMERS <= icmpv6rpl_vars.timerIdDIO)
    {
        return;
    }

    if (icmpv6rpl_allowSendingDIO() == TRUE)
    {
        if (opentrickletimers_getValue(0) == 0)
        {
            opentrickletimers_start(icmpv6rpl_vars.timerIdDIO);
        }
        else
        {
            opentrickletimers_reset(icmpv6rpl_vars.timerIdDIO);
        }
    }
}

void icmpv6rpl_writeDODAGid(uint8_t *dodagid)
{

    // write DODAGID to DIO/DAO
    memcpy(
        &(icmpv6rpl_vars.dio.DODAGID[0]),
        dodagid,
        sizeof(icmpv6rpl_vars.dio.DODAGID));
    memcpy(
        &(icmpv6rpl_vars.dao.DODAGID[0]),
        dodagid,
        sizeof(icmpv6rpl_vars.dao.DODAGID));

    // remember I got a DODAGID
    icmpv6rpl_vars.fDodagidWritten = 1;
}

uint8_t icmpv6rpl_getRPLIntanceID(void)
{
    return icmpv6rpl_vars.dao.rplinstanceId;
}

owerror_t icmpv6rpl_getRPLDODAGid(uint8_t *address_128b)
{
    if (icmpv6rpl_vars.fDodagidWritten)
    {
        memcpy(address_128b, icmpv6rpl_vars.dao.DODAGID, 16);
        return E_SUCCESS;
    }
    return E_FAIL;
}

/**
\brief Called when DIO/DAO was sent.

\param[in] msg   Pointer to the message just sent.
\param[in] error Outcome of the sending.
*/
void icmpv6rpl_sendDone(OpenQueueEntry_t *msg, owerror_t error)
{

    // take ownership over that packet
    msg->owner = COMPONENT_ICMPv6RPL;

    // make sure I created it
    if (msg->creator != COMPONENT_ICMPv6RPL)
    {
        LOG_ERROR(COMPONENT_ICMPv6RPL, ERR_UNEXPECTED_SENDDONE,
                  (errorparameter_t)0,
                  (errorparameter_t)0);
    }

    uint8_t code = ((ICMPv6_ht *)(msg->payload))->code;

    // I'm not busy sending DIO/DAO anymore
    if (packetfunctions_isBroadcastMulticast(&(msg->l2_nextORpreviousHop)))
    {

        if(code == IANA_ICMPv6_RPL_DIO){
            icmpv6rpl_vars.busySendingDIO = FALSE;
            if(error == E_SUCCESS){
                icmpv6rpl_vars.count_dio_done += 1;
                if(msg->note == 1) icmpv6rpl_vars.count_dio_trickle_done += 1;
            }
        }

#if RPL_DIS_TRANSMISSION == TRUE
        if(code == IANA_ICMPv6_RPL_DIS){
            icmpv6rpl_vars.busySendingDIS = FALSE;
        }
#endif

    }
    else
    {
        icmpv6rpl_vars.busySendingDAO = FALSE;
        if (error == E_SUCCESS)
        {
            icmpv6rpl_vars.dao_numFail = 0;
        }
        else
        {
            icmpv6rpl_vars.dao_numFail++;
        }
    }

    // free packet
    openqueue_freePacketBuffer(msg);
}

/**
\brief Called when RPL message received.

\param[in] msg   Pointer to the received message.
*/
void icmpv6rpl_receive(OpenQueueEntry_t *msg)
{
    uint8_t icmpv6code;

    // take ownership
    msg->owner = COMPONENT_ICMPv6RPL;

    // retrieve ICMPv6 code
    icmpv6code = (((ICMPv6_ht *)(msg->payload))->code);

    // toss ICMPv6 header
    packetfunctions_tossHeader(&msg, sizeof(ICMPv6_ht));

    // handle message
    switch (icmpv6code)
    {
    case IANA_ICMPv6_RPL_DIS:
        // rfc6550#section-8.3
        // A node SHOULD NOT reset its DIO Trickle timer in response to unicast DIS messages
        // When a node receives a unicast DIS, it MUST unicast a DIO to the sender in response.

        if (icmpv6rpl_isPreferredParent(&msg->l2_nextORpreviousHop))
        {
            // We receive a DIS from our preferred parent, indicating that our parent has left Join State 5.
            // wisun_neighbors_neighborUnreachable(icmpv6rpl_vars.ParentIndex);
            break;
        }
        else
        {
            if (packetfunctions_isBroadcastMulticast(&msg->l3_destinationAdd) == TRUE)
            {
                icmpv6rpl_start_or_reset_trickle_timer();
            }
            sendDIO(FALSE, TRUE);
        }

        break;
    case IANA_ICMPv6_RPL_DIO:
        if (idmanager_getIsDAGroot() == TRUE)
        {
            // stop here if I'm in the DAG root
            break; // break, don't return
        }

        if (IEEE802154_security_isConfigured() == FALSE)
        {
            // this DIO is not able to be parsed if the mote is not secure yet
            break;
        }
        // update routing info for that neighbor
        icmpv6rpl_indicateRxDIO(msg);
        break;
    case IANA_ICMPv6_RPL_DAO:
        // this should never happen
        LOG_ERROR(COMPONENT_ICMPv6RPL, ERR_UNEXPECTED_DAO,
                  (errorparameter_t)0,
                  (errorparameter_t)0);
        break;
    default:
        // this should never happen
        LOG_ERROR(COMPONENT_ICMPv6RPL, ERR_MSG_UNKNOWN_TYPE,
                  (errorparameter_t)icmpv6code,
                  (errorparameter_t)0);
        break;
    }

    // free message
    openqueue_freePacketBuffer(msg);
}

/**
\brief Retrieve this mote's parent index in neighbor table.

\returns TRUE and index of parent if have one, FALSE if no parent
*/
bool icmpv6rpl_getPreferredParentIndex(uint8_t *indexptr)
{
    *indexptr = icmpv6rpl_vars.ParentIndex;
    return icmpv6rpl_vars.haveParent;
}

bool icmpv6rpl_allowSendingDIO(void)
{
    if (idmanager_getIsDAGroot() == TRUE)
    {
        return TRUE;
    }
    else
    {
        return icmpv6rpl_vars.haveParent;
    }
}

/**
\brief Retrieve my preferred parent's EUI64 address.
\param[out] addressToWrite Where to copy the preferred parent's address to.
*/
bool icmpv6rpl_getPreferredParentEui64(open_addr_t *addressToWrite)
{
    if (
        icmpv6rpl_vars.haveParent &&
        neighbors_getNeighborNoResource(icmpv6rpl_vars.ParentIndex) == FALSE)
    {
        return neighbors_getNeighborEui64(addressToWrite, ADDR_64B, icmpv6rpl_vars.ParentIndex);
    }

    return FALSE;
}

/**
\brief Indicate whether some neighbor is the routing parent.

\param[in] address The EUI64 address of the neighbor.

\returns TRUE if that neighbor is preferred parent, FALSE otherwise.
*/
bool icmpv6rpl_isPreferredParent(open_addr_t *address)
{
    open_addr_t temp;
    // do we currently have a parent?
    if (icmpv6rpl_vars.haveParent == FALSE)
    {
        return FALSE;
    }

    // compare parent address to the one presented.
    switch (address->type)
    {
    case ADDR_64B:
        neighbors_getNeighborEui64(&temp, ADDR_64B, icmpv6rpl_vars.ParentIndex);
        return packetfunctions_sameAddress(address, &temp);
    default:
        LOG_CRITICAL(COMPONENT_ICMPv6RPL, ERR_WRONG_ADDR_TYPE,
                     (errorparameter_t)address->type,
                     (errorparameter_t)3);
        return FALSE;
    }
}

/**
\brief Retrieve this mote's current DAG rank.

\returns This mote's current DAG rank.
*/
dagrank_t icmpv6rpl_getMyDAGrank(void)
{
    return icmpv6rpl_vars.myDAGrank;
}

/**
\brief Direct intervention to set the value of DAG rank in the data structure

Meant for direct control from command on serial port or from test application,
bypassing the routing protocol!
*/
void icmpv6rpl_setMyDAGrank(dagrank_t rank)
{
    icmpv6rpl_vars.myDAGrank = rank;
}

/**
\brief Routing algorithm
*/
void icmpv6rpl_updateMyDAGrankAndParentSelection(void)
{
    uint8_t i;
    uint16_t previousDAGrank;
    uint16_t prevRankIncrease;
    uint8_t prevParentIndex;
    bool prevHadParent;
    bool foundBetterParent;
    // temporaries
    uint16_t rankIncrease;
    dagrank_t neighborRank;
    uint32_t tentativeDAGrank;

    open_addr_t newParent;

    // if I'm a DAGroot, my DAGrank is always MINHOPRANKINCREASE
    if ((idmanager_getIsDAGroot()) == TRUE)
    {
        // the dagrank is not set through setting command, set rank to MINHOPRANKINCREASE here
        if (icmpv6rpl_vars.myDAGrank != MINHOPRANKINCREASE)
        { // test for change so as not to report unchanged value when root
            icmpv6rpl_vars.myDAGrank = MINHOPRANKINCREASE;
        }
        return;
    }
    // prep for loop, remember state before neighbor table scanning
    prevParentIndex = icmpv6rpl_vars.ParentIndex;
    prevHadParent = icmpv6rpl_vars.haveParent;
    prevRankIncrease = icmpv6rpl_vars.rankIncrease;
    // update my rank to current parent first
    if (icmpv6rpl_vars.haveParent == TRUE)
    {
        if (neighbors_getNeighborNoResource(icmpv6rpl_vars.ParentIndex) == TRUE)
        {
            icmpv6rpl_vars.myDAGrank = 65535;
        }
        else
        {
            if (neighbors_reachedMinimalTransmission(icmpv6rpl_vars.ParentIndex) == FALSE)
            {
                // I havn't enough transmission to my parent, don't update.
                return;
            }
            rankIncrease = neighbors_getLinkMetric(icmpv6rpl_vars.ParentIndex);
            neighborRank = neighbors_getNeighborRank(icmpv6rpl_vars.ParentIndex);
            tentativeDAGrank = (uint32_t)neighborRank + rankIncrease;
            if (tentativeDAGrank > 65535)
            {
                icmpv6rpl_vars.myDAGrank = 65535;
            }
            else
            {
                icmpv6rpl_vars.myDAGrank = (uint16_t)tentativeDAGrank;
            }
        }
    }
    previousDAGrank = icmpv6rpl_vars.myDAGrank;
    foundBetterParent = FALSE;
    icmpv6rpl_vars.haveParent = FALSE;

    // loop through neighbor table, update myDAGrank
    for (i = 0; i < MAXNUMNEIGHBORS; i++)
    {
        if (neighbors_isStableNeighborByIndex(i))
        { // in use and link is stable
            // neighbor marked as NORES can't be parent
            if (
                neighbors_getNeighborNoResource(i) == TRUE)
            {
                continue;
            }
            // get link cost to this neighbor
            rankIncrease = neighbors_getLinkMetric(i);
            // get this neighbor's advertized rank
            neighborRank = neighbors_getNeighborRank(i);
            // if this neighbor has unknown/infinite rank, pass on it
            if (neighborRank == DEFAULTDAGRANK)
                continue;
            // compute tentative cost of full path to root through this neighbor
            tentativeDAGrank = (uint32_t)neighborRank + rankIncrease;
            if (tentativeDAGrank > 65535)
            {
                tentativeDAGrank = 65535;
            }
            // if larger than lowestRank+maxRankIncrease, pass (per rfc6550#section-8.2.2.4)
            if (
                icmpv6rpl_vars.lowestRankInHistory < (MAXDAGRANK - DAGMAXRANKINCREASE) &&
                tentativeDAGrank > (icmpv6rpl_vars.lowestRankInHistory + DAGMAXRANKINCREASE))
            {
                continue;
            }
            // if not low enough to justify switch, pass (i.e. hysterisis)
            if (
                (previousDAGrank < tentativeDAGrank) ||
                (previousDAGrank - tentativeDAGrank < 2 * MINHOPRANKINCREASE))
            {
                continue;
            }
            // remember that we have at least one valid candidate parent
            foundBetterParent = TRUE;
            // select best candidate so far
            if (icmpv6rpl_vars.myDAGrank > tentativeDAGrank)
            {
                if (tentativeDAGrank < icmpv6rpl_vars.lowestRankInHistory)
                {
                    icmpv6rpl_vars.lowestRankInHistory = (uint16_t)tentativeDAGrank;
                }
                icmpv6rpl_vars.myDAGrank = (uint16_t)tentativeDAGrank;
                icmpv6rpl_vars.ParentIndex = i;
                icmpv6rpl_vars.rankIncrease = rankIncrease;
            }
        }
    }

    if (foundBetterParent)
    {
        icmpv6rpl_vars.haveParent = TRUE;
        if (!prevHadParent)
        {
            // in case preParent is killed before calling this function, clear the preferredParent flag
            neighbors_setPreferredParent(prevParentIndex, FALSE);
            // set neighbors as preferred parent
            neighbors_setPreferredParent(icmpv6rpl_vars.ParentIndex, TRUE);

            // update the upstream traffic nexthop address to new parent
            neighbors_getNeighborEui64(&newParent, ADDR_64B, icmpv6rpl_vars.ParentIndex);
            icmpv6rpl_updateNexthopAddress(&newParent);

            senddao_();
            icmpv6rpl_start_or_reset_trickle_timer();
        }
        else
        {
            if (icmpv6rpl_vars.ParentIndex == prevParentIndex)
            {
                // report on the rank change if any, not on the deletion/creation of parent
                if (icmpv6rpl_vars.myDAGrank != previousDAGrank)
                {
                }
                else
                {
                    // same parent, same rank, nothing to report about
                }
            }
            else
            {
                // clear neighbors preferredParent flag
                neighbors_setPreferredParent(prevParentIndex, FALSE);
                // set neighbors as preferred parent
                neighbors_setPreferredParent(icmpv6rpl_vars.ParentIndex, TRUE);

                // update the upstream traffic nexthop address to new parent
                neighbors_getNeighborEui64(&newParent, ADDR_64B, icmpv6rpl_vars.ParentIndex);
                icmpv6rpl_updateNexthopAddress(&newParent);

                senddao_();
                icmpv6rpl_start_or_reset_trickle_timer();
            }
        }

        // Log
        uint16_t prId2B;
        uint8_t asn[5];
        asn_t curAsn;

        prId2B = (newParent.addr_64b[6] << 8) | newParent.addr_64b[7];
        icmpv6rpl_debug.prId2B = prId2B;
        icmpv6rpl_debug.myDAGrank = icmpv6rpl_vars.myDAGrank;
        icmpv6rpl_debug.slotDuration = (ieee154e_getSlotDuration() * 305) / 10000;

        ieee154e_getAsn(&(asn[0]));
        curAsn.bytes0and1 = 256 * asn[1] + asn[0];
        curAsn.bytes2and3 = 256 * asn[3] + asn[2];
        curAsn.byte4 = asn[4];
        
        memcpy(&icmpv6rpl_debug.asn, &curAsn, sizeof(asn_t));
        openserial_print_exp(COMPONENT_ICMPv6RPL, ERR_EXPERIMENT, (uint8_t *) & icmpv6rpl_debug, sizeof(icmpv6rpl_debug_t));

        icmpv6periodic_begin();
    }
    else
    {
        // restore routing table as we found it on entry
        icmpv6rpl_vars.myDAGrank = previousDAGrank;
        icmpv6rpl_vars.ParentIndex = prevParentIndex;
        icmpv6rpl_vars.haveParent = prevHadParent;
        icmpv6rpl_vars.rankIncrease = prevRankIncrease;
        // no change to report on
    }

    // if my rank is reached to MAXDAGRANK
    if (icmpv6rpl_vars.myDAGrank == MAXDAGRANK)
    {
        icmpv6rpl_vars.lowestRankInHistory = MAXDAGRANK;
    }

#if RPL_DIS_TRANSMISSION == TRUE
    if (icmpv6rpl_vars.haveParent == FALSE || icmpv6rpl_vars.myDAGrank == MAXDAGRANK)
    {
        opentrickletimers_stop(icmpv6rpl_vars.timerIdDIO);
        opentimers_scheduleIn(
            icmpv6rpl_vars.timerIdDIS,
            1000,
            TIME_MS,
            TIMER_PERIODIC,
            icmpv6rpl_timer_DIS_cb);
    }
#endif
}

/**
\brief In case of parent changed, update the nexthop of the IPv6 packet in the queue

\param newParent. the new parent address
*/
void icmpv6rpl_updateNexthopAddress(open_addr_t *newParent)
{

    openqueue_updateNextHopPayload(newParent);
}

/**
\brief Indicate I just received a RPL DIO from a neighbor.

This function should be called for each received a DIO is received so neighbor
routing information in the neighbor table can be updated.

The fields which are updated are:
- DAGrank

\param[in] msg The received message with msg->payload pointing to the DIO
   header.
*/
void icmpv6rpl_indicateRxDIO(OpenQueueEntry_t *msg)
{
    uint8_t i;
    uint8_t temp_8b;
    dagrank_t neighborRank;
    open_addr_t NeighborAddress;
    open_addr_t myPrefix;
    uint8_t *current;
    int16_t optionsLen;
    // take ownership over the packet
    msg->owner = COMPONENT_ICMPv6RPL;

    // update some fields of our DIO
    memcpy(
        &(icmpv6rpl_vars.dio),
        (icmpv6rpl_dio_ht *)(msg->payload),
        sizeof(icmpv6rpl_dio_ht));

    // write DODAGID in DIO and DAO
    icmpv6rpl_writeDODAGid(&(((icmpv6rpl_dio_ht *)(msg->payload))->DODAGID[0]));

    // save pointer to incoming DIO header in global structure for simplfying debug.
    icmpv6rpl_vars.incomingDio = (icmpv6rpl_dio_ht *)(msg->payload);
    current = msg->payload + sizeof(icmpv6rpl_dio_ht);
    optionsLen = msg->length - sizeof(icmpv6rpl_dio_ht);

    while (optionsLen > 0)
    {
        switch (current[0])
        {
        case RPL_OPTION_CONFIG:
            // configuration option
            icmpv6rpl_vars.incomingConf = (icmpv6rpl_config_ht *)(current);

            icmpv6rpl_vars.incomingConf->maxRankIncrease = (icmpv6rpl_vars.incomingConf->maxRankIncrease << 8) | (icmpv6rpl_vars.incomingConf->maxRankIncrease >> 8);
            icmpv6rpl_vars.incomingConf->minHopRankIncrease = (icmpv6rpl_vars.incomingConf->minHopRankIncrease << 8) | (icmpv6rpl_vars.incomingConf->minHopRankIncrease >> 8);
            icmpv6rpl_vars.incomingConf->OCP = (icmpv6rpl_vars.incomingConf->OCP << 8) | (icmpv6rpl_vars.incomingConf->OCP >> 8);
            icmpv6rpl_vars.incomingConf->lifetimeUnit = (icmpv6rpl_vars.incomingConf->lifetimeUnit << 8) | (icmpv6rpl_vars.incomingConf->lifetimeUnit >> 8);

            memcpy(&icmpv6rpl_vars.conf, icmpv6rpl_vars.incomingConf, sizeof(icmpv6rpl_config_ht));

            // do whatever needs to be done with the configuration option of RPL
            optionsLen = optionsLen - current[1] - 2;
            current = current + current[1] + 2;
            break;
        case RPL_OPTION_PIO:
            // pio
            icmpv6rpl_vars.incomingPio = (icmpv6rpl_pio_t *)(current);
            // update PIO with the received one.
            memcpy(&icmpv6rpl_vars.pio, icmpv6rpl_vars.incomingPio, sizeof(icmpv6rpl_pio_t));
            // update my prefix from PIO
            // looks like we adopt the prefix from any PIO without a question about this node being our parent??
            myPrefix.type = ADDR_PREFIX;
            memcpy(
                myPrefix.prefix,
                icmpv6rpl_vars.incomingPio->prefix,
                sizeof(myPrefix.prefix));
            idmanager_setMyID(&myPrefix);
            optionsLen = optionsLen - current[1] - 2;
            current = current + current[1] + 2;
            break;
        case RPL_OPTION_PAD1:
        case RPL_OPTION_PADN:
            // this is the end of DIO message, just ignore the padding
            optionsLen = 0;
            break;
        default:
            // option not supported, just jump the len;
            optionsLen = optionsLen - current[1] - 2;
            current = current + current[1] + 2;
            break;
        }
        if (optionsLen < 0)
        {
            // length 필드 값이 맞지 않음
            return;
        }
    }

    // quick fix: rank is two bytes in network order: need to swap bytes
    temp_8b = *(msg->payload + 2);
    icmpv6rpl_vars.incomingDio->rank = (temp_8b << 8) + *(msg->payload + 3);

    // update rank in DIO as well (which will be overwritten with my rank when send).
    icmpv6rpl_vars.dio.rank = icmpv6rpl_vars.incomingDio->rank;

    if (icmpv6rpl_vars.incomingDio->rank == MAXDAGRANK)
    {
        if (icmpv6rpl_allowSendingDIO() == TRUE)
        {
            icmpv6rpl_start_or_reset_trickle_timer();
        }
    }

    // update rank of that neighbor in table
    for (i = 0; i < MAXNUMNEIGHBORS; i++)
    {
        if (neighbors_getNeighborEui64(&NeighborAddress, ADDR_64B, i))
        { // this neighbor entry is in use
            if (packetfunctions_sameAddress(&(msg->l2_nextORpreviousHop), &NeighborAddress))
            { // matching address
                neighborRank = neighbors_getNeighborRank(i);
                if (icmpv6rpl_vars.incomingDio->rank == neighborRank)
                {
                    opentrickletimers_recvConsistent(icmpv6rpl_vars.timerIdDIO);
                }

                if (
                    (icmpv6rpl_vars.incomingDio->rank > neighborRank) &&
                    (icmpv6rpl_vars.incomingDio->rank - neighborRank) >
                        ((3 * DEFAULTLINKCOST - 2) * MINHOPRANKINCREASE))
                {
                    // the new DAGrank looks suspiciously high, only increment a bit
                    neighbors_setNeighborRank(i, neighborRank + ((3 * DEFAULTLINKCOST - 2) * 2 * MINHOPRANKINCREASE));
                    LOG_ERROR(COMPONENT_ICMPv6RPL, ERR_LARGE_DAGRANK,
                              (errorparameter_t)icmpv6rpl_vars.incomingDio->rank,
                              (errorparameter_t)neighborRank);
                }
                else
                {
                    neighbors_setNeighborRank(i, icmpv6rpl_vars.incomingDio->rank);
                }
                // since changes were made to neighbors DAG rank, run the routing algorithm again
                icmpv6rpl_updateMyDAGrankAndParentSelection();
                break; // there should be only one matching entry, no need to loop further
            }
        }
    }
}

void icmpv6rpl_killPreferredParent(void)
{
    uint8_t neighborParentIndex;

    icmpv6rpl_vars.haveParent = FALSE;
    icmpv6rpl_vars.ParentIndex = -1;
    if (icmpv6rpl_getPreferredParentIndex(&neighborParentIndex) == TRUE)
    {
        neighbors_setPreferredParent(neighborParentIndex, FALSE);
    }
    icmpv6rpl_vars.dao_retransmissionTime = 0;
    icmpv6rpl_vars.dao_numFail = 0;

    if (idmanager_getIsDAGroot() == TRUE)
    {
        icmpv6rpl_vars.myDAGrank = MINHOPRANKINCREASE;
    }
    else
    {
        icmpv6rpl_vars.myDAGrank = DEFAULTDAGRANK;
    }

    // remove packets genereted by this module (DIO and DAO) from openqueue
    openqueue_removeAllCreatedBy(COMPONENT_ICMPv6RPL);

    icmpv6rpl_vars.busySendingDIO = FALSE;
    icmpv6rpl_vars.busySendingDAO = FALSE;
}

#if RPL_DIS_TRANSMISSION == TRUE
// DIS
/*
\brief Returns whether the current DIS message is being created.
To check if the packet is DIS so that DIS transmission is possible even before the preferred parent is determined.
*/
bool icmpv6rpl_isCreatingDIS(void)
{
    return icmpv6rpl_vars.creatingDIS;
}
#endif

//=========================== private =========================================

#if RPL_DIS_TRANSMISSION == TRUE
//===== DIS-related

/**
\brief DIS timer callback function.

\note This timer callback function is executed in task mode by opentimer
    already. No need to push a task again.
*/
void icmpv6rpl_timer_DIS_cb(opentimers_id_t id)
{
    icmpv6rpl_timer_DIS_task();
}

/**
\brief Handler for DIS timer event.

\note This function is executed in task context, called by the scheduler.
*/
void icmpv6rpl_timer_DIS_task(void)
{
    if (openrandom_get16b() < (0xffff / DIS_PORTION))
    {
        sendDIS();
    }
}

/**
\brief Prepare and a send a RPL DIS.
*/
void sendDIS(void)
{
    OpenQueueEntry_t *msg;
    open_addr_t addressToWrite;

    memset(&addressToWrite, 0, sizeof(open_addr_t));

    if (ieee154e_isSynch() == FALSE)
    {
        return;
    }

    // dont' send a DIS if you're the DAG root
    if (idmanager_getIsDAGroot())
    {
        return;
    }

    // dont' send a DIS if you have parent & rank
    if (icmpv6rpl_getPreferredParentEui64(&addressToWrite) &&
        icmpv6rpl_getMyDAGrank() != MAXDAGRANK)
    {

        icmpv6rpl_vars.busySendingDIS = FALSE;

        // finally you have parent, cancel the timer but do not destroy it
        opentimers_cancel(icmpv6rpl_vars.timerIdDIS);

        return;
    }

    // dont' send a DIS if you're still busy sending the previous one
    if (icmpv6rpl_vars.busySendingDIS == TRUE)
    {
        return;
    }

    // all good to send DIS
    msg = openqueue_getFreePacketBuffer(COMPONENT_ICMPv6RPL);
    if (msg == NULL)
    {
        LOG_ERROR(COMPONENT_ICMPv6RPL, ERR_NO_FREE_PACKET_BUFFER,
                  (errorparameter_t)0,
                  (errorparameter_t)0);
        return;
    }

    // take ownership
    msg->creator = COMPONENT_ICMPv6RPL;
    msg->owner = COMPONENT_ICMPv6RPL;

    // set transport information
    msg->l4_protocol = IANA_ICMPv6;
    msg->l4_protocol_compressed = FALSE;
    msg->l4_sourcePortORicmpv6Type = IANA_ICMPv6_RPL;

    // set DIS destination
    memcpy(&(msg->l3_destinationAdd), &icmpv6rpl_vars.disDestination, sizeof(open_addr_t));

    //=== DIS header
    if (packetfunctions_reserveHeader(&msg, sizeof(icmpv6rpl_dis_ht)) == E_FAIL)
    {
        openqueue_freePacketBuffer(msg);
        return;
    }
    memcpy(
        ((icmpv6rpl_dis_ht *)(msg->payload)),
        &(icmpv6rpl_vars.dis),
        sizeof(icmpv6rpl_dis_ht));

    //=== ICMPv6 header
    if (packetfunctions_reserveHeader(&msg, sizeof(ICMPv6_ht)) == E_FAIL)
    {
        openqueue_freePacketBuffer(msg);
        return;
    }
    ((ICMPv6_ht *)(msg->payload))->type = msg->l4_sourcePortORicmpv6Type;
    ((ICMPv6_ht *)(msg->payload))->code = IANA_ICMPv6_RPL_DIS;
    packetfunctions_calculateChecksum(msg, (uint8_t *)&(((ICMPv6_ht *)(msg->payload))->checksum)); // call last

    //===== send
    icmpv6rpl_vars.creatingDIS = TRUE;

    icmpv6rpl_vars.count_dis += 1;
    if (icmpv6_send(msg) == E_SUCCESS)
    {
        icmpv6rpl_vars.busySendingDIS = TRUE;
    }
    else
    {
        openqueue_freePacketBuffer(msg);
    }
    icmpv6rpl_vars.creatingDIS = FALSE;
}
#endif // RPL_DIS_TRANSMISSION == TRUE

//===== DIO-related

/**
\brief DIO timer callback function.

\note This timer callback function is executed in task mode by opentimer
    already. No need to push a task again.
*/
void icmpv6rpl_timer_DIO_cb(opentimers_id_t id)
{
    sendDIO(TRUE, FALSE);
}

/**
\brief Prepare and a send a RPL DIO.
*/
owerror_t sendDIO(bool is_trickle, bool is_priority)
{
    OpenQueueEntry_t *msg;
    open_addr_t addressToWrite;

    memset(&addressToWrite, 0, sizeof(open_addr_t));

    // stop if I'm not sync'ed
    if (ieee154e_isSynch() == FALSE)
    {

        // remove packets genereted by this module (DIO and DAO) from openqueue
        openqueue_removeAllCreatedBy(COMPONENT_ICMPv6RPL);

        // I'm not busy sending a DIO/DAO
        icmpv6rpl_vars.busySendingDIO = FALSE;
        icmpv6rpl_vars.busySendingDAO = FALSE;

        // stop here
        return E_FAIL;
    }

    // do not send DIO if I have the default DAG rank
    if (icmpv6rpl_getMyDAGrank() == DEFAULTDAGRANK)
    {
        return E_FAIL;
    }

    if (
        idmanager_getIsDAGroot() == FALSE &&
        (icmpv6rpl_getPreferredParentEui64(&addressToWrite) == FALSE ||
         (icmpv6rpl_getPreferredParentEui64(&addressToWrite) &&
          schedule_hasNegotiatedCellToNeighbor(&addressToWrite, CELLTYPE_TX) == FALSE)))
    {
        // delete packets genereted by this module (EB and KA) from openqueue
        openqueue_removeAllCreatedBy(COMPONENT_ICMPv6RPL);

        // I'm not busy sending a DIO/DAO
        icmpv6rpl_vars.busySendingDIO = FALSE;
        icmpv6rpl_vars.busySendingDAO = FALSE;

        return E_FAIL;
    }

    // dont' send a DIO if you're still busy sending the previous one
    if (icmpv6rpl_vars.busySendingDIO == TRUE)
    {
        return E_FAIL;
    }

    // if you get here, all good to send a DIO

    // reserve a free packet buffer for DIO
    
    msg = openqueue_getFreePacketBuffer(COMPONENT_ICMPv6RPL);
#if use_qtrickle == TRUE
    if(is_priority == TRUE && msg == NULL){
        msg = openqueue_getFreePacketBufferPriority(COMPONENT_ICMPv6RPL);
    }
#endif

    if (msg == NULL)
    {
        LOG_ERROR(COMPONENT_ICMPv6RPL, ERR_NO_FREE_PACKET_BUFFER,
                  (errorparameter_t)1,
                  (errorparameter_t)0);

        return E_FAIL;
    }

    // take ownership
    msg->creator = COMPONENT_ICMPv6RPL;
    msg->owner = COMPONENT_ICMPv6RPL;

    // set transport information
    msg->l4_protocol = IANA_ICMPv6;
    msg->l4_protocol_compressed = FALSE;
    msg->l4_sourcePortORicmpv6Type = IANA_ICMPv6_RPL;

    // set DIO destination
    memcpy(&(msg->l3_destinationAdd), &icmpv6rpl_vars.dioDestination, sizeof(open_addr_t));

    //===== Configuration option
    if (packetfunctions_reserveHeader(&msg, sizeof(icmpv6rpl_config_ht)) == E_FAIL)
    {
        openqueue_freePacketBuffer(msg);
        return E_FAIL;
    }

    // copy the PIO in the packet
    memcpy(
        ((icmpv6rpl_config_ht *)(msg->payload)),
        &(icmpv6rpl_vars.conf),
        sizeof(icmpv6rpl_config_ht));

    ((icmpv6rpl_config_ht *)(msg->payload))->maxRankIncrease = (icmpv6rpl_vars.conf.maxRankIncrease << 8) | (icmpv6rpl_vars.conf.maxRankIncrease >> 8);
    ((icmpv6rpl_config_ht *)(msg->payload))->minHopRankIncrease = (icmpv6rpl_vars.conf.minHopRankIncrease << 8) | (icmpv6rpl_vars.conf.minHopRankIncrease >> 8);
    ((icmpv6rpl_config_ht *)(msg->payload))->OCP = (icmpv6rpl_vars.conf.OCP << 8) | (icmpv6rpl_vars.conf.OCP >> 8);
    ((icmpv6rpl_config_ht *)(msg->payload))->lifetimeUnit = (icmpv6rpl_vars.conf.lifetimeUnit << 8) | (icmpv6rpl_vars.conf.lifetimeUnit >> 8);

    //===== PIO payload

    if (packetfunctions_reserveHeader(&msg, sizeof(icmpv6rpl_pio_t)) == E_FAIL)
    {
        openqueue_freePacketBuffer(msg);
        return E_FAIL;
    }

    // copy my prefix into the PIO
    memcpy(
        &(icmpv6rpl_vars.pio.prefix[0]),
        idmanager_getMyID(ADDR_PREFIX)->prefix,
        sizeof(idmanager_getMyID(ADDR_PREFIX)->prefix));
    // host address is not needed. Only prefix.
    memcpy(
        &(icmpv6rpl_vars.pio.prefix[8]),
        idmanager_getMyID(ADDR_64B)->addr_64b,
        sizeof(idmanager_getMyID(ADDR_64B)->addr_64b));

    // copy the PIO in the packet
    memcpy(
        ((icmpv6rpl_pio_t *)(msg->payload)),
        &(icmpv6rpl_vars.pio),
        sizeof(icmpv6rpl_pio_t));

    //===== DIO payload
    // note: DIO is already mostly populated
    icmpv6rpl_vars.dio.rank = icmpv6rpl_getMyDAGrank();
    if (packetfunctions_reserveHeader(&msg, sizeof(icmpv6rpl_dio_ht)) == E_FAIL)
    {
        openqueue_freePacketBuffer(msg);
        return E_FAIL;
    }
    memcpy(
        ((icmpv6rpl_dio_ht *)(msg->payload)),
        &(icmpv6rpl_vars.dio),
        sizeof(icmpv6rpl_dio_ht));

    // reverse the rank bytes order in Big Endian
    *(msg->payload + 2) = (icmpv6rpl_vars.dio.rank >> 8) & 0xFF;
    *(msg->payload + 3) = icmpv6rpl_vars.dio.rank & 0xFF;

    //===== ICMPv6 header
    if (packetfunctions_reserveHeader(&msg, sizeof(ICMPv6_ht)) == E_FAIL)
    {
        openqueue_freePacketBuffer(msg);
        return E_FAIL;
    }
    ((ICMPv6_ht *)(msg->payload))->type = msg->l4_sourcePortORicmpv6Type;
    ((ICMPv6_ht *)(msg->payload))->code = IANA_ICMPv6_RPL_DIO;
    packetfunctions_calculateChecksum(msg, (uint8_t *)&(((ICMPv6_ht *)(msg->payload))->checksum)); // call last

    // send
    icmpv6rpl_vars.count_dio += 1;
    if(is_trickle) icmpv6rpl_vars.count_dio_trickle += 1;
    if (icmpv6_send(msg) == E_SUCCESS)
    {
        icmpv6rpl_vars.busySendingDIO = TRUE;
    }
    else
    {
        openqueue_freePacketBuffer(msg);
        return E_FAIL;
    }

    return E_SUCCESS;
}

//===== DAO-related

/**
\brief DAO timer callback function.

\note This timer callback function is executed in task mode by opentimer
    already. No need to push a task again.
*/
void icmpv6rpl_timer_DAO_cb(opentimers_id_t id)
{

    icmpv6rpl_timer_DAO_task();
}

/**
\brief Handler for DAO timer event.

\note This function is executed in task context, called by the scheduler.
*/
void icmpv6rpl_timer_DAO_task(void)
{
    // this is DAO retransmission
    if (icmpv6rpl_vars.dao_numFail <= RPL_DAO_MAX_NUM_RETX)
    {
        if (sendDAO() == E_FAIL)
        {
            // DAO transmission failure (not send), reset retransmission time
            icmpv6rpl_vars.dao_retransmissionTime = 0;
        }
    }
    icmpv6rpl_dao_calculateRetransmissionTime();
    icmpv6rpl_dao_scheduleTimer(icmpv6rpl_vars.dao_retransmissionTime);
}

void icmpv6rpl_dao_scheduleTimer(uint32_t duration)
{
    opentimers_scheduleIn(
        icmpv6rpl_vars.timerIdDAO,
        duration,
        TIME_MS,
        TIMER_ONESHOT,
        icmpv6rpl_timer_DAO_cb);
}

void icmpv6rpl_dao_calculateRetransmissionTime(void)
{
    float rand_num;

    // generate 0 ~ 0.1 value
    rand_num = (float)(openrandom_get16b() % 100) / 1000.0;
    // random number between -0.1 to 0.1
    if ((openrandom_get16b() % 10) < 5)
    {
        rand_num = -1 * (rand_num);
    }

    // calculate retransmission time
    if (icmpv6rpl_vars.dao_retransmissionTime == 0)
    {
        icmpv6rpl_vars.dao_retransmissionTime = DAO_TIMEOUT + rand_num * DAO_TIMEOUT;
    }
    else
    {
        icmpv6rpl_vars.dao_retransmissionTime = 2 * icmpv6rpl_vars.dao_retransmissionTime + rand_num * icmpv6rpl_vars.dao_retransmissionTime;
    }

    // limit upper bound
    if (icmpv6rpl_vars.dao_retransmissionTime > DAO_MAX_RT)
    {
        icmpv6rpl_vars.dao_retransmissionTime = DAO_MAX_RT + rand_num * DAO_MAX_RT;
    }
}

/**
\brief Prepare and a send a RPL DAO.
*/
owerror_t sendDAO(void)
{
    OpenQueueEntry_t *msg;                       // pointer to DAO messages
    uint8_t nbrIdx;                              // running neighbor index
    uint8_t numTargetParents, numTransitParents; // the number of parents indicated in transit option
    open_addr_t address;
    open_addr_t *prefix;

    memset(&address, 0, sizeof(open_addr_t));

    if (ieee154e_isSynch() == FALSE)
    {
        // I'm not sync'ed

        // delete packets genereted by this module (DIO and DAO) from openqueue
        openqueue_removeAllCreatedBy(COMPONENT_ICMPv6RPL);

        // I'm not busy sending a DIO/DAO
        icmpv6rpl_vars.busySendingDAO = FALSE;
        icmpv6rpl_vars.busySendingDIO = FALSE;

        // stop here
        return E_FAIL;
    }

    // dont' send a DAO if you're the DAG root
    if (idmanager_getIsDAGroot() == TRUE)
    {
        return E_FAIL;
    }

    // dont' send a DAO if you did not acquire a DAGrank
    if (icmpv6rpl_getMyDAGrank() == DEFAULTDAGRANK)
    {
        return E_FAIL;
    }

    if (
        icmpv6rpl_getPreferredParentEui64(&address) == FALSE ||
        (icmpv6rpl_getPreferredParentEui64(&address) &&
         schedule_hasNegotiatedCellToNeighbor(&address, CELLTYPE_TX) == FALSE))
    {
        // delete packets genereted by this module (EB and KA) from openqueue
        openqueue_removeAllCreatedBy(COMPONENT_ICMPv6RPL);

        // I'm not busy sending a DIO/DAO
        icmpv6rpl_vars.busySendingDIO = FALSE;
        icmpv6rpl_vars.busySendingDAO = FALSE;

        return E_FAIL;
    }

    memset(&address, 0, sizeof(open_addr_t));

    // dont' send a DAO if you're still busy sending the previous one
    if (icmpv6rpl_vars.busySendingDAO == TRUE)
    {
        return E_FAIL;
    }

    // if you get here, you start construct DAO

    // reserve a free packet buffer for DAO
    msg = openqueue_getFreePacketBuffer(COMPONENT_ICMPv6RPL);
    if (msg == NULL)
    {
        LOG_ERROR(COMPONENT_ICMPv6RPL, ERR_NO_FREE_PACKET_BUFFER,
                  (errorparameter_t)2,
                  (errorparameter_t)0);
        return E_FAIL;
    }

    // take ownership
    msg->creator = COMPONENT_ICMPv6RPL;
    msg->owner = COMPONENT_ICMPv6RPL;

    // set transport information
    msg->l4_protocol = IANA_ICMPv6;
    msg->l4_sourcePortORicmpv6Type = IANA_ICMPv6_RPL;

    // set DAO destination
    msg->l3_destinationAdd.type = ADDR_128B;
    memcpy(msg->l3_destinationAdd.addr_128b, icmpv6rpl_vars.dio.DODAGID, sizeof(icmpv6rpl_vars.dio.DODAGID));

    //===== fill in packet

    // NOTE: the number of DAO transit addresses to send 2: preferred parent & alternate parent (if available)
    //=== transit option -- from RFC 6550, page 55 - 1 transit information header per parent is required.

    numTransitParents = 0;
    icmpv6rpl_getPreferredParentEui64(&address);
    if (packetfunctions_writeAddress(&msg, &address, OW_BIG_ENDIAN) == E_FAIL)
    {
        openqueue_freePacketBuffer(msg);
        return E_FAIL;
    }
    prefix = idmanager_getMyID(ADDR_PREFIX);
    if (packetfunctions_writeAddress(&msg, prefix, OW_BIG_ENDIAN) == E_FAIL)
    {
        openqueue_freePacketBuffer(msg);
        return E_FAIL;
    }

    icmpv6rpl_vars.dao_transit.optionLength = LENGTH_ADDR128b + sizeof(icmpv6rpl_dao_transit_ht) - 2;
    icmpv6rpl_vars.dao_transit.PathControl = 0; // PC1 11000000
    icmpv6rpl_vars.dao_transit.type = OPTION_TRANSIT_INFORMATION_TYPE;

    // write transit info in packet
    if (packetfunctions_reserveHeader(&msg, sizeof(icmpv6rpl_dao_transit_ht)) == E_FAIL)
    {
        openqueue_freePacketBuffer(msg);
        return E_FAIL;
    }
    memcpy(
        ((icmpv6rpl_dao_transit_ht *)(msg->payload)),
        &(icmpv6rpl_vars.dao_transit),
        sizeof(icmpv6rpl_dao_transit_ht));
    numTransitParents++;

    // target information is required. RFC 6550 page 55.
    /*
    One or more Transit Information options MUST be preceded by one or
    more RPL Target options.
    */
    numTargetParents = 0;
    for (nbrIdx = 0; nbrIdx < MAXNUMNEIGHBORS; nbrIdx++)
    {
        if ((neighbors_isNeighborWithHigherDAGrank(nbrIdx)) == TRUE)
        {
            // this neighbor is of higher DAGrank as I am. so it is my child

            // write it's address in DAO RFC6550 page 80 check point 1.
            neighbors_getNeighborEui64(&address, ADDR_64B, nbrIdx);
            if (packetfunctions_writeAddress(&msg, &address, OW_BIG_ENDIAN) == E_FAIL)
            {
                openqueue_freePacketBuffer(msg);
                return E_FAIL;
            }
            prefix = idmanager_getMyID(ADDR_PREFIX);
            if (packetfunctions_writeAddress(&msg, prefix, OW_BIG_ENDIAN) == E_FAIL)
            {
                openqueue_freePacketBuffer(msg);
                return E_FAIL;
            }

            icmpv6rpl_vars.dao_target.optionLength = LENGTH_ADDR128b + sizeof(icmpv6rpl_dao_target_ht) - 2; // no header type and length
            icmpv6rpl_vars.dao_target.type = OPTION_TARGET_INFORMATION_TYPE;
            icmpv6rpl_vars.dao_target.flags = 0;          // must be 0
            icmpv6rpl_vars.dao_target.prefixLength = 128; // 128 leading bits  -- full address.

            // write transit info in packet
            if (packetfunctions_reserveHeader(&msg, sizeof(icmpv6rpl_dao_target_ht)) == E_FAIL)
            {
                openqueue_freePacketBuffer(msg);
                return E_FAIL;
            }
            memcpy(
                ((icmpv6rpl_dao_target_ht *)(msg->payload)),
                &(icmpv6rpl_vars.dao_target),
                sizeof(icmpv6rpl_dao_target_ht));

            // remember I found it
            numTargetParents++;
        }
        // limit to MAX_TARGET_PARENTS the number of DAO target addresses to send
        // section 8.2.1 pag 67 RFC6550 -- using a subset
        //  poipoi TODO base selection on ETX rather than first X.
        if (numTargetParents >= MAX_TARGET_PARENTS)
            break;
    }

    // stop here if no parents found
    if (numTransitParents == 0)
    {
        openqueue_freePacketBuffer(msg);
        return E_FAIL;
    }

    icmpv6rpl_vars.dao_transit.PathSequence++; // increment path sequence.
    // if you get here, you will send a DAO

    //=== DAO header
    if (packetfunctions_reserveHeader(&msg, sizeof(icmpv6rpl_dao_ht)) == E_FAIL)
    {
        openqueue_freePacketBuffer(msg);
        return E_FAIL;
    }
    icmpv6rpl_vars.dao.DAOSequence++;
    memcpy(
        ((icmpv6rpl_dao_ht *)(msg->payload)),
        &(icmpv6rpl_vars.dao),
        sizeof(icmpv6rpl_dao_ht));

    //=== ICMPv6 header
    if (packetfunctions_reserveHeader(&msg, sizeof(ICMPv6_ht)) == E_FAIL)
    {
        openqueue_freePacketBuffer(msg);
        return E_FAIL;
    }
    ((ICMPv6_ht *)(msg->payload))->type = msg->l4_sourcePortORicmpv6Type;
    ((ICMPv6_ht *)(msg->payload))->code = IANA_ICMPv6_RPL_DAO;
    packetfunctions_calculateChecksum(msg, (uint8_t *)&(((ICMPv6_ht *)(msg->payload))->checksum)); // call last

    //===== send
    if (icmpv6_send(msg) == E_SUCCESS)
    {
        icmpv6rpl_vars.busySendingDAO = TRUE;
        icmpv6rpl_vars.daoSent = TRUE;
    }
    else
    {
        openqueue_freePacketBuffer(msg);
        return E_FAIL;
    }

    return E_SUCCESS;
}

/**
\brief call send DAO function.
\this function is called by other module.
*/
void senddao_(void)
{
    sendDAO();
}

// depreciated
void icmpv6rpl_setDIOPeriod(uint16_t dioPeriod)
{
    return;
}

// depreciated
void icmpv6rpl_setDAOPeriod(uint16_t daoPeriod)
{
    return;
}

bool icmpv6rpl_daoSent(void)
{
    if (idmanager_getIsDAGroot() == TRUE)
    {
        return TRUE;
    }
    return icmpv6rpl_vars.daoSent;
}

uint16_t icmpv6rpl_get_failed_dio(bool is_trickle, bool failed_or_count)
{
    uint16_t count_;
    uint16_t transmit_;

    if (is_trickle) {
        count_ = icmpv6rpl_vars.count_dio_trickle;
        transmit_ = icmpv6rpl_vars.count_dio_trickle_done;
    }else{
        count_ = icmpv6rpl_vars.count_dio;
        transmit_ = icmpv6rpl_vars.count_dio_done;
    }

    uint16_t failed = count_ - transmit_;
    if (failed < 0) LOG_CRITICAL(COMPONENT_ICMPv6RPL, ERR_UNDER_OVER_VALUE, 1, failed);
    if (count_ == 0) return EMPTY_16;
    if (failed_or_count == FALSE) return failed;
    return count_;
}


void icmpv6rpl_resetAll(void)
{
    icmpv6rpl_killPreferredParent();

    icmpv6rpl_vars.dao_retransmissionTime = 0;
    icmpv6rpl_vars.dao_numFail = 0;

    if (idmanager_getIsDAGroot() == TRUE)
    {
        icmpv6rpl_vars.myDAGrank = MINHOPRANKINCREASE;
        icmpv6rpl_vars.lowestRankInHistory = MINHOPRANKINCREASE;
    }
    else
    {
        icmpv6rpl_vars.myDAGrank = MAXDAGRANK;
        icmpv6rpl_vars.lowestRankInHistory = MAXDAGRANK;
    }

    icmpv6rpl_vars.daoSent = FALSE;
#if RPL_DIS_TRANSMISSION == TRUE
    icmpv6rpl_vars.busySendingDIS = FALSE;
    icmpv6rpl_vars.creatingDIS = FALSE;
#endif
    icmpv6rpl_vars.busySendingDIO = FALSE;
    icmpv6rpl_vars.busySendingDAO = FALSE;

    icmpv6rpl_vars.fDodagidWritten = 0;
}
