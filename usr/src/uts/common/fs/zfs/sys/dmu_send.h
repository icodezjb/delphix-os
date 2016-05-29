/*
 * CDDL HEADER START
 *
 * The contents of this file are subject to the terms of the
 * Common Development and Distribution License (the "License").
 * You may not use this file except in compliance with the License.
 *
 * You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
 * or http://www.opensolaris.org/os/licensing.
 * See the License for the specific language governing permissions
 * and limitations under the License.
 *
 * When distributing Covered Code, include this CDDL HEADER in each
 * file and include the License file at usr/src/OPENSOLARIS.LICENSE.
 * If applicable, add the following below this CDDL HEADER, with the
 * fields enclosed by brackets "[]" replaced with your own identifying
 * information: Portions Copyright [yyyy] [name of copyright owner]
 *
 * CDDL HEADER END
 */

/*
 * Copyright (c) 2005, 2010, Oracle and/or its affiliates. All rights reserved.
 * Copyright (c) 2012, 2016 by Delphix. All rights reserved.
 * Copyright 2011 Nexenta Systems, Inc. All rights reserved.
 * Copyright (c) 2013, Joyent, Inc. All rights reserved.
 */

#ifndef _DMU_SEND_H
#define	_DMU_SEND_H

#include <sys/inttypes.h>
#include <sys/spa.h>
#include <sys/objlist.h>
#include <sys/dsl_bookmark.h>

struct vnode;
struct dsl_dataset;
struct drr_begin;
struct avl_tree;
struct dmu_replay_record;
struct dmu_send_outparams;

extern const char *recv_clone_name;

int dmu_send(const char *tosnap, const char *fromsnap, boolean_t embedok,
    boolean_t large_block_ok, boolean_t compressok,
    uint64_t resumeobj, uint64_t resumeoff,
    nvlist_t *redactsnaps, const char *redactbook, const char *redactlist_book,
    int outfd, offset_t *off, struct dmu_send_outparams *dso);
int dmu_send_estimate_fast(struct dsl_dataset *ds, struct dsl_dataset *fromds,
    boolean_t stream_compressed, uint64_t *sizep);
int dmu_send_obj(const char *pool, uint64_t tosnap, uint64_t fromsnap,
    boolean_t embedok, boolean_t large_block_ok, boolean_t compressok,
    int outfd, offset_t *off, struct dmu_send_outparams *dso);

typedef struct dmu_recv_cookie {
	struct dsl_dataset *drc_ds;
	struct dmu_replay_record *drc_drr_begin;
	struct drr_begin *drc_drrb;
	const char *drc_tofs;
	const char *drc_tosnap;
	boolean_t drc_newfs;
	boolean_t drc_byteswap;
	boolean_t drc_force;
	boolean_t drc_resumable;
	struct avl_tree *drc_guid_to_ds_map;
	uint64_t drc_newsnapobj;
	void *drc_owner;
	cred_t *drc_cred;
	nvlist_t *drc_begin_nvl;

	objset_t *drc_os;
	vnode_t *drc_vp; /* The vnode to read the stream from */
	uint64_t drc_voff; /* The current offset in the stream */
	uint64_t drc_bytes_read;
	/*
	 * A record that has had its payload read in, but hasn't yet been handed
	 * off to the worker thread.
	 */
	struct receive_record_arg *drc_rrd;
	/* A record that has had its header read in, but not its payload. */
	struct receive_record_arg *drc_next_rrd;
	zio_cksum_t drc_cksum;
	zio_cksum_t drc_prev_cksum;
	int drc_err;
	/* Sorted list of objects not to issue prefetches for. */
	objlist_t *drc_ignore_objlist;
} dmu_recv_cookie_t;

typedef int (*dmu_send_outfunc_t)(void *buf, int len, void *arg);
typedef struct dmu_send_outparams {
	dmu_send_outfunc_t	dso_outfunc;
	void			*dso_arg;
	boolean_t		dso_dryrun;
} dmu_send_outparams_t;

#define	REDACT_BLOCK_MAX_COUNT (1ULL << 48)

inline uint64_t
redact_block_get_size(redact_block_phys_t *rbp)
{
	return (BF64_GET_SB((rbp)->rbp_size_count, 48, 16, SPA_MINBLOCKSHIFT,
	    0));
}

inline void
redact_block_set_size(redact_block_phys_t *rbp, uint64_t size)
{
	BF64_SET_SB((rbp)->rbp_size_count, 48, 16, SPA_MINBLOCKSHIFT, 0, size);
}

inline uint64_t
redact_block_get_count(redact_block_phys_t *rbp)
{
	return (BF64_GET_SB((rbp)->rbp_size_count, 0, 48, 0, 1));
}

inline void
redact_block_set_count(redact_block_phys_t *rbp, uint64_t count)
{
	BF64_SET_SB((rbp)->rbp_size_count, 0, 48, 0, 1, count);
}

int dmu_recv_begin(char *tofs, char *tosnap,
    struct dmu_replay_record *drr_begin,
    boolean_t force, boolean_t resumable, char *origin, dmu_recv_cookie_t *drc,
    vnode_t *vp, offset_t *voffp);
int dmu_recv_stream(dmu_recv_cookie_t *drc, int cleanup_fd,
    uint64_t *action_handlep, offset_t *voffp);
int dmu_recv_end(dmu_recv_cookie_t *drc, void *owner);
boolean_t dmu_objset_is_receiving(objset_t *os);

#endif /* _DMU_SEND_H */
