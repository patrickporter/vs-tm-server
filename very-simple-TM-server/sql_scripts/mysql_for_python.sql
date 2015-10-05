CREATE TABLE `users` (
	`username`	VARCHAR(150) NOT NULL,
	`password`	VARCHAR(150) NOT NULL,
	`is_admin`	int(1) NOT NULL,
	PRIMARY KEY(username)
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `groups` (
	`group_name`	VARCHAR(150) NOT NULL,
	PRIMARY KEY(group_name)
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `group_memberships` (
	`group_membership_id`	int(11) NOT NULL AUTO_INCREMENT,
	`group`	VARCHAR(150) NOT NULL,
	`user`	VARCHAR(150) NOT NULL,
	PRIMARY KEY(group_membership_id),
	FOREIGN KEY(`group`) REFERENCES groups(group_name),
	FOREIGN KEY(`user`) REFERENCES users ( username )
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `tms` (
	`tm_id` int(11) AUTO_INCREMENT,
	`name`	VARCHAR(100) NOT NULL,
	`orig_filename`	VARCHAR(500) DEFAULT NULL,
	`sourcelang`	CHAR(6),
	`targetlang`	CHAR(6),
	`owner`	VARCHAR(100),
	`readonly_group`	VARCHAR(100),
	`readwrite_group`	VARCHAR(100),
	`created_datetime`	DATE NOT NULL,
	`last_updated_datetime`	DATE,
	PRIMARY KEY(tm_id)
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `tus` (
  `tu_id` int(11) NOT NULL AUTO_INCREMENT,
  `tm_id` int(11) NOT NULL,
  `sourcetext` text NOT NULL,
  `targettext` text NOT NULL,
  `created_by` varchar(200) DEFAULT NULL,
  `created_date` datetime DEFAULT NULL,
  `changed_by` varchar(200) DEFAULT NULL,
  `changed_date` datetime DEFAULT NULL,
  `last_used_date` datetime DEFAULT NULL,
  PRIMARY KEY (`tu_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TRIGGER `on_tus_delete` AFTER DELETE
ON `tus` FOR EACH ROW
BEGIN
   UPDATE `tms` SET `last_updated_datetime`= NOW() WHERE `tm_id` = old.`tm_id`;
END;

CREATE TRIGGER `on_tus_update` AFTER UPDATE 
ON `tus` FOR EACH ROW
BEGIN
   UPDATE `tms` SET `last_updated_datetime`= NOW() WHERE `tm_id` = new.`tm_id`;
END;

CREATE TRIGGER `tus_AFTER_INSERT` AFTER INSERT ON `tus` FOR EACH ROW
BEGIN
UPDATE `tms` SET `last_updated_datetime`= NOW() WHERE `tm_id` = new.`tm_id`;
END;