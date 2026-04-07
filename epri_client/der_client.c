// Copyright (c) 2018 Electric Power Research Institute, Inc.
// author: Mark Slicker <mark.slicker@gmail.com>

#include <stdio.h>

#include "se_core.h"
#include "client.c"
#include "list_util.c"
#include "time.c"
#include "event.c"
#include "hash.c"
#include "resource.c"
#include "retrieve.c"
// #include "subscribe.c"
#include "schedule.c"
#include "der.c"
#include "metering.c"

char *timestamp () {
  time_t now = (time_t)se_time ();
  return ctime (&now);
}

// ---------------------------------------------------------------------------
// JSON event emission
// Writes a single EVENT_JSON: line to stdout for each DER event transition.
// Python reads stdout and filters for this prefix to receive structured events.
// All other output (printf elsewhere in the codebase) is treated as debug log.
// ---------------------------------------------------------------------------

static void emit_event_json (EventBlock *eb, const char *type) {
  Resource *r = eb->event;
  DerDevice *device = eb->context;
  SE_Event_t *ev = r->data;
  int i;

  printf ("EVENT_JSON:{\"type\":\"%s\",\"sfdi\":%lu", type,
          (unsigned long) device->sfdi);

  printf (",\"mrid\":\"");
  for (i = 0; i < 16; i++) printf ("%02x", (unsigned int) ev->mRID[i]);
  printf ("\"");

  printf (",\"description\":\"%s\"", ev->description);

  if (strcmp (type, "start") == 0 && r->type == SE_DERControl) {
    SE_DERControl_t *derc = r->data;
    SE_DERControlBase_t *b = &derc->DERControlBase;
    int first = 1;
    printf (",\"control\":{");

    if (b->_flags & SE_opModFixedW_exists) {
      printf ("\"opModFixedW\":%d", (int) b->opModFixedW);
      first = 0;
    }
    if (b->_flags & SE_opModMaxLimW_exists) {
      if (!first) printf (",");
      printf ("\"opModMaxLimW\":%u", (unsigned int) b->opModMaxLimW);
      first = 0;
    }
    if (b->_flags & SE_opModTargetW_exists) {
      if (!first) printf (",");
      printf ("\"opModTargetW\":%d", (int) b->opModTargetW.value);
      first = 0;
    }
    if (b->_flags & SE_opModFixedVar_exists) {
      if (!first) printf (",");
      printf ("\"opModFixedVar\":%d", (int) b->opModFixedVar.value);
      first = 0;
    }
    if (b->_flags & SE_opModTargetVar_exists) {
      if (!first) printf (",");
      printf ("\"opModTargetVar\":%d", (int) b->opModTargetVar.value);
      first = 0;
    }
    if (b->_flags & SE_rampTms_exists) {
      if (!first) printf (",");
      printf ("\"rampTms\":%u", (unsigned int) b->rampTms);
      first = 0;
    }
    if (b->_flags & SE_opModConnect_exists) {
      if (!first) printf (",");
      printf ("\"opModConnect\":%s",
              (b->_flags & SE_opModConnect_true) ? "true" : "false");
      first = 0;
    }
    if (b->_flags & SE_opModEnergize_exists) {
      if (!first) printf (",");
      printf ("\"opModEnergize\":%s",
              (b->_flags & SE_opModEnergize_true) ? "true" : "false");
    }
    printf ("}");
  }

  printf ("}\n");
  fflush (stdout);
}

// ---------------------------------------------------------------------------

void print_event_start (EventBlock *eb) { Resource *r = eb->event;
  DerDevice *device = eb->context;
  SE_Event_t *ev = r->data; SE_DERControl_t *derc;
  printf ("Event Start \"%s\" -- %s", ev->description, timestamp ());
  printf ("EndDevice: %ld\n", device->sfdi);
  switch (r->type) {
  case SE_DERControl: derc = r->data;
    print_se_object (&derc->DERControlBase, SE_DERControlBase);
  } printf ("\n");
  emit_event_json (eb, "start");
}

void print_event_end (EventBlock *eb) { Resource *r = eb->event;
  DerDevice *device = eb->context; SE_Event_t *ev = r->data;
  printf ("Event End \"%s\" -- %s", ev->description, timestamp ());
  printf ("EndDevice: %ld\n\n", device->sfdi);
  emit_event_json (eb, "end");
}

void print_default_control (DerDevice *device) {
  SE_DefaultDERControl_t *dc = device->dderc;
  printf ("Default Control \"%s\" -- %s", dc->description, timestamp ());
  printf ("EndDevice: %ld\n", device->sfdi);
  print_se_object (dc, SE_DefaultDERControl);
  printf ("\n");
}

void print_blocks (EventBlock *eb) {
  while (eb) {
    SE_Event_t *ev = resource_data (eb->event);
    printf ("  %-11ld %-11ld %-31s\n", eb->start, eb->end, ev->description);
    eb = eb->next;
  }
}

void print_event_schedule (DerDevice *d) {
  Schedule *s = &d->schedule; EventBlock *eb = s->scheduled;
  printf ("Event Schedule for device %ld -- %s", d->sfdi, timestamp ());
  printf ("  Start       End         Description\n");
  print_blocks (s->scheduled);
  printf ("Active Blocks:\n");
  print_blocks (s->active); printf ("\n");
}

int der_poll (void **any, int timeout) {
  Schedule *s; int event;
  while (event = next_event (any)) {
    switch (event) {
    case SCHEDULE_UPDATE: s = *any; update_schedule (s);
      if (!s->active) { DerDevice *d = s->context;
	if (d->dderc) insert_event (d, DEFAULT_CONTROL, 0);
      } break;
    case RESOURCE_POLL: poll_resource (*any);
    case RESOURCE_UPDATE: update_resource (*any); break;
    case RESOURCE_REMOVE:
      if (se_event (resource_type (*any)))
	delete_blocks (*any);
    case RETRIEVE_FAIL:
      remove_stub (*any); break;
    default: return event;
    }
  }
  return client_poll (any, timeout);
}

void der_init () {
  device_init (); resource_init (); event_init ();
}
