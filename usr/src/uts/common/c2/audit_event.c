aui_null,	AUE_NULL,	aus_null,	/* 7 (loadable) was wait */
aui_null,	AUE_NULL,	aus_null,	/* 11 (loadable) was exec */
		auf_mknod,	0,
aui_null,	AUE_NULL,	aus_null,	/* 22 (loadable) was umount */
		auf_null,	0,
aui_null,	AUE_NULL,	aus_null,	/* 48 (loadable) was ssig */
		auf_null,	0,
aui_null,	AUE_NULL,	aus_null,	/* 101 (loadable) */
aui_null,	AUE_NULL,	aus_null,	/* 102 (loadable) */
/* chmod start function */
/* chmod start function */
		/*
		 * convert file pointer to file descriptor
		 *   Note: fd ref count incremented here.
		 */
		/* get path from file struct here */
	switch (fm & (O_RDONLY|O_WRONLY|O_RDWR|O_CREAT|O_TRUNC)) {
	if (error != EPERM)
	/* not auditing this event, nothing then to do */
	if (tad->tad_flag == 0)
	error = lookupname(pnamep, UIO_USERSPACE, NO_FOLLOW, &dvp, NULLVPP);