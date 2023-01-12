#ifndef OPENWSN_ICMPv6RPL_H
#define OPENWSN_ICMPv6RPL_H

/**
\addtogroup IPv6
\{
\addtogroup ICMPv6RPL
\{
*/

#include "opendefs.h"
#include "opentimers.h"

//=========================== define ==========================================

#define DEFAULT_RPL_MAXRANKINCREASE 0
#define DEFAULT_RPL_OCP 1 // MRHOF
#define DEFAULT_RPL_DEFAULTLIFETIME 120
#define DEFAULT_RPL_LIFETIMEUNIT 60
#define DEFAULT_RPL_MINHOPRANKINCREASE 128

// Whether or not to transmit DIS (TRUE or FALSE)
// FANWG line 1034:
// A FAN Router node MAY wait for DIO messages, MAY solicit a DIO by issuing a unicast
// DIS to a likely neighbor, or MAY solicit a DIO by issuing a multicast DIS.
// It is RECOMMENDED that multicast DIS be used only when necessary.
#define RPL_DIS_TRANSMISSION TRUE

#define RPL_DAO_INTERVAL_MS (60 * 1000) // 1 minute, static situation
#define RPL_DAO_MAX_NUM_RETX 3          // A total of (RPL_DAO_MAX_NUM_RETX + 1) DAO transmissions

// DODAG RPLInstanceID, Version Number, DTSN set to DUT specific value, set by Border Router
#define DEFAULT_RPL_RPLINSTANCEID 0x00
#define DEFAULT_RPL_VERSIONNUMBER 0x00
#define DEFAULT_RPL_DTSN 0x33

// Non-Storing Mode of Operation (1)
#define MOP_DIO_A 0 << 5
#define MOP_DIO_B 0 << 4
#define MOP_DIO_C 1 << 3
// least preferred (0)
#define PRF_DIO_A 0 << 2
#define PRF_DIO_B 0 << 1
#define PRF_DIO_C 0 << 0
// Grounded (1)
#define G_DIO 1 << 7

#define FLAG_DAO_A 0 << 0
#define FLAG_DAO_B 0 << 1
#define FLAG_DAO_C 0 << 2
#define FLAG_DAO_D 0 << 3
#define FLAG_DAO_E 0 << 4
#define FLAG_DAO_F 0 << 5
#define D_DAO 1 << 6
#define K_DAO 0 << 7

#define E_DAO_Transit_Info 0 << 7

#define PC1_A_DAO_Transit_Info 0 << 7
#define PC1_B_DAO_Transit_Info 1 << 6

#define PC2_A_DAO_Transit_Info 0 << 5
#define PC2_B_DAO_Transit_Info 0 << 4

#define PC3_A_DAO_Transit_Info 0 << 3
#define PC3_B_DAO_Transit_Info 0 << 2

#define PC4_A_DAO_Transit_Info 0 << 1
#define PC4_B_DAO_Transit_Info 0 << 0

#define Prf_A_dio_options 0 << 4
#define Prf_B_dio_options 0 << 3

#define DEFAULT_PATH_CONTROL_SIZE 7

#define RPL_OPTION_PIO 0x8
#define RPL_OPTION_CONFIG 0x4
#define RPL_OPTION_PAD1 0x0
#define RPL_OPTION_PADN 0x1

#define RPL_DAO_ACK_STATUS_UNQUALIFIED_ACCEPTANCE 0

// max number of parents and children to send in DAO
// section 8.2.1 pag 67 RFC6550 -- using a subset
#define MAX_TARGET_PARENTS 0x01

// DAO retransmission
#define DAO_TIMEOUT 5000
#define DAO_MAX_RT RPL_DAO_INTERVAL_MS

enum
{
   OPTION_ROUTE_INFORMATION_TYPE = 0x03,
   OPTION_DODAG_CONFIGURATION_TYPE = 0x04,
   OPTION_TARGET_INFORMATION_TYPE = 0x05,
   OPTION_TRANSIT_INFORMATION_TYPE = 0x06,
};

//=========================== typedef =========================================

//===== DIS
/**
\brief Header format of a RPL DIS packet.
*/
BEGIN_PACK
typedef struct
{
   uint8_t flags;
   uint8_t reserved;
} icmpv6rpl_dis_ht;
END_PACK

//===== DIO

/**
\brief Header format of a RPL DIO packet.
*/
BEGIN_PACK
typedef struct
{
   uint8_t rplinstanceId; ///< set by the DODAG root.
   uint8_t verNumb;
   dagrank_t rank;
   uint8_t rplOptions;
   uint8_t DTSN;
   uint8_t flags;
   uint8_t reserved;
   uint8_t DODAGID[16];
} icmpv6rpl_dio_ht;
END_PACK

BEGIN_PACK
typedef struct
{
   uint8_t type;
   uint8_t optLen;
   uint8_t prefLen;
   uint8_t flags;
   uint32_t vlifetime;
   uint32_t plifetime;
   uint32_t reserved;
   uint8_t prefix[16];
} icmpv6rpl_pio_t;
END_PACK

BEGIN_PACK
typedef struct
{
   uint8_t type;
   uint8_t optLen;
   uint8_t flagsAPCS;
   uint8_t DIOIntDoubl;
   uint8_t DIOIntMin;
   uint8_t DIORedun;
   uint16_t maxRankIncrease;
   uint16_t minHopRankIncrease;
   uint16_t OCP;
   uint8_t reserved;
   uint8_t defLifetime;
   uint16_t lifetimeUnit;
} icmpv6rpl_config_ht;
END_PACK

//===== DAO

/**
\brief Header format of a RPL DAO packet.
*/
BEGIN_PACK
typedef struct
{
   uint8_t rplinstanceId; ///< set by the DODAG root.
   uint8_t K_D_flags;
   uint8_t reserved;
   uint8_t DAOSequence;
   uint8_t DODAGID[16];
} icmpv6rpl_dao_ht;
END_PACK

/**
\brief Header format of a RPL DAO "Transit Information" option.
*/
BEGIN_PACK
typedef struct
{
   uint8_t type; ///< set by the DODAG root.
   uint8_t optionLength;
   uint8_t E_flags;
   uint8_t PathControl;
   uint8_t PathSequence;
   uint8_t PathLifetime;
} icmpv6rpl_dao_transit_ht;
END_PACK

/**
\brief Header format of a RPL DAO "Target" option.
*/
BEGIN_PACK
typedef struct
{
   uint8_t type; ///< set by the DODAG root.
   uint8_t optionLength;
   uint8_t flags;
   uint8_t prefixLength;
} icmpv6rpl_dao_target_ht;
END_PACK

//=========================== module variables ================================

typedef struct
{
   // admin
#if RPL_DIS_TRANSMISSION == TRUE
   bool busySendingDIS; ///< currently sending DIS.
   bool creatingDIS;    ///< currently creating DIS.
#endif
   bool busySendingDIO;     ///< currently sending DIO.
   bool busySendingDAO;     ///< currently sending DAO.
   uint8_t fDodagidWritten; ///< is DODAGID already written to DIO/DAO?

#if RPL_DIS_TRANSMISSION == TRUE
   // DIS-related
   icmpv6rpl_dis_ht dis;
   open_addr_t disDestination;
   opentimers_id_t timerIdDIS;
#endif

   // DIO-related
   icmpv6rpl_dio_ht dio; ///< pre-populated DIO packet.
   icmpv6rpl_pio_t pio;  ///< pre-populated PIO com
   icmpv6rpl_config_ht conf;
   open_addr_t dioDestination; ///< IPv6 destination address for DIOs.
   uint16_t dioTimerCounter;   ///< counter to determine when to send DIO.
   opentimers_id_t timerIdDIO; ///< ID of the timer used to send DIOs.

   // DAO-related
   icmpv6rpl_dao_ht dao;                 ///< pre-populated DAO packet.
   icmpv6rpl_dao_transit_ht dao_transit; ///< pre-populated DAO "Transit Info" option header.
   icmpv6rpl_dao_target_ht dao_target;   ///< pre-populated DAO "Transit Info" option header.
   opentimers_id_t timerIdDAO;           ///< ID of the timer used to maintenance DAOs.
   uint32_t dao_retransmissionTime;      ///< DAO retransmission time using binary exponential retransmission mechanism
   uint8_t dao_numFail;                  ///< Number of consecutive DAO transmission failures (MAC tx failure or DAO-ACK reception failure)
   open_addr_t dao_targetAddr;           ///< DAO Target Information, Target Address

   // routing table
   dagrank_t myDAGrank;           ///< rank of this router within DAG.
   dagrank_t lowestRankInHistory; ///< lowest Rank that the node has advertised

   uint16_t rankIncrease; ///< the cost of the link to the parent, in units of rank
   bool haveParent;       ///< this router has a route to DAG root
   int8_t ParentIndex;    ///< index of Parent in neighbor table (iff haveParent==TRUE)

   // actually only here for debug
   icmpv6rpl_dio_ht *incomingDio;     // keep it global to be able to debug correctly.
   icmpv6rpl_pio_t *incomingPio;      // pio structure incoming
   icmpv6rpl_config_ht *incomingConf; // configuration incoming
   bool daoSent;
   bool dioSent;
   bool dioScheduled;
} icmpv6rpl_vars_t;

BEGIN_PACK
typedef struct
{
   uint16_t prId2B;
   uint16_t myDAGrank;
   uint8_t slotDuration;
   asn_t asn;
} icmpv6rpl_debug_t;
END_PACK

//=========================== prototypes ======================================

void icmpv6rpl_init(void);
void icmpv6rpl_sendDone(OpenQueueEntry_t *msg, owerror_t error);
void icmpv6rpl_receive(OpenQueueEntry_t *msg);
void icmpv6rpl_writeDODAGid(uint8_t *dodagid);
uint8_t icmpv6rpl_getRPLIntanceID(void);
owerror_t icmpv6rpl_getRPLDODAGid(uint8_t *address_128b);
void icmpv6rpl_setDIOPeriod(uint16_t dioPeriod);
void icmpv6rpl_setDAOPeriod(uint16_t daoPeriod);
bool icmpv6rpl_getPreferredParentIndex(uint8_t *indexptr);
bool icmpv6rpl_allowSendingDIO(void);
void icmpv6rpl_start_or_reset_trickle_timer(void);
bool icmpv6rpl_getPreferredParentEui64(open_addr_t *addressToWrite);

#if RPL_DIS_TRANSMISSION == TRUE
// DIS
bool icmpv6rpl_isCreatingDIS(void);
#endif

void icmpv6rpl_updateNexthopAddress(open_addr_t *addressToWrite);
bool icmpv6rpl_isPreferredParent(open_addr_t *address);
dagrank_t icmpv6rpl_getMyDAGrank(void);
void icmpv6rpl_setMyDAGrank(dagrank_t rank);
void icmpv6rpl_killPreferredParent(void);
void icmpv6rpl_updateMyDAGrankAndParentSelection(void);
void icmpv6rpl_indicateRxDIO(OpenQueueEntry_t *msg);
void senddao_(void);
bool icmpv6rpl_daoSent(void);
bool icmpv6rpl_getdioSent(void);
void icmpv6rpl_setdioSent(bool value);
bool icmpv6rpl_getdioScheduled(void);
void icmpv6rpl_setdioScheduled(bool value);
void icmpv6rpl_resetAll(void);

/**
\}
\}
*/

#endif /* OPENWSN_ICMPv6RPL_H */
