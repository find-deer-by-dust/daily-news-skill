
create database emailbotdb;

CREATE TABLE IF NOT EXISTS `dailyNews` (
	`id` INTEGER NOT NULL AUTO_INCREMENT UNIQUE COMMENT '主键',
	`date` DATE NOT NULL COMMENT '日期' ,
	`news` TEXT NOT NULL COMMENT '新闻',
	`aiReply` TEXT NOT NULL COMMENT 'ai对新闻回应',
	PRIMARY KEY(`id`)
) COMMENT='每日新闻表';



