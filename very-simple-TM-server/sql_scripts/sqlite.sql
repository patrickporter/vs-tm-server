CREATE TABLE "add_tm_events" (
	`id`	INTEGER,
	`timestamp`	TEXT
);

CREATE TABLE "users" (
	`username`	TEXT NOT NULL,
	`password`	TEXT NOT NULL,
	`is_admin`	NUMERIC DEFAULT 0,
	PRIMARY KEY(username)
);

CREATE TABLE "groups" (
	`group_name`	TEXT NOT NULL,
	PRIMARY KEY(group_name)
);

CREATE TABLE "group_memberships" (
	`group_membership_id`	INTEGER,
	`group`	TEXT NOT NULL,
	`user`	TEXT NOT NULL,
	PRIMARY KEY(group_membership_id),
	FOREIGN KEY(`group`) REFERENCES groups(group_name),
	FOREIGN KEY(`user`) REFERENCES users ( username )
);

CREATE TABLE "tms" (
	`tm_id`	INTEGER,
	`name`	TEXT NOT NULL,
	`orig_filename`	TEXT NOT NULL,
	`sourcelang`	CHAR(6),
	`targetlang`	CHAR(6),
	`owner`	TEXT,
	`readonly_group`	TEXT,
	`readwrite_group`	TEXT,
	`created_datetime`	TEXT NOT NULL,
	`last_updated_datetime`	TEXT,
	PRIMARY KEY(tm_id)
);

CREATE TABLE "tus" (
  `tu_id` INTEGER PRIMARY KEY,
  `tm_id`           INT    NOT NULL,
  `sourcetext`            TEXT,
  `targettext`           TEXT,
  `created_by`          TEXT,
  `created_date`          TEXT,
  `changed_by`          TEXT,
  `changed_date`          TEXT,
  `last_used_date`          TEXT,
  FOREIGN KEY(tm_id) REFERENCES tms(tm_id));

CREATE TRIGGER log_tm_insert AFTER INSERT 
ON `tms`
BEGIN
  UPDATE `tms` SET `tm_id`=((SELECT count(*) from `add_tm_events`)+1) WHERE `tms`.`tm_id`=new.`tm_id`;
  INSERT INTO `add_tm_events`(id, timestamp) VALUES ((SELECT count(*) from `add_tm_events`) + 1, datetime('now'));
END;

CREATE TRIGGER on_tus_delete AFTER DELETE 
ON `tus`
BEGIN
   UPDATE `tms` SET `last_updated_datetime`=datetime('now') WHERE `tm_id` = old.`tm_id`;
END;

CREATE TRIGGER on_tus_update AFTER UPDATE 
ON `tus`
BEGIN
   UPDATE `tms` SET `last_updated_datetime`=datetime('now') WHERE `tm_id` = new.`tm_id`;
END;

CREATE TRIGGER on_tus_insert AFTER INSERT 
ON `tus`
BEGIN
   UPDATE `tms` SET `last_updated_datetime`=datetime('now') WHERE `tm_id` = new.`tm_id`;
END;