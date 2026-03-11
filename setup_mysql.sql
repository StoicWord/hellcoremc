-- ═══════════════════════════════════════════════════════
-- HELLCORE NETWORK — MySQL Setup Script
-- Run this in MySQL Workbench, phpMyAdmin, or terminal:
--   mysql -u root -p < setup_mysql.sql
-- ═══════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS hellcore CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE hellcore;

CREATE TABLE IF NOT EXISTS hc_users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  email         VARCHAR(200) UNIQUE NOT NULL,
  username      VARCHAR(50)  UNIQUE NOT NULL,
  mc_username   VARCHAR(50)  DEFAULT '',
  password_hash VARCHAR(100) NOT NULL,
  session_token VARCHAR(120),
  role          VARCHAR(30)  DEFAULT 'player',
  created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hc_ranks (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  user_id    INT NOT NULL,
  gamemode   VARCHAR(30) NOT NULL,
  rank_name  VARCHAR(30) DEFAULT 'default',
  UNIQUE KEY uq (user_id, gamemode)
);

CREATE TABLE IF NOT EXISTS hc_economy (
  user_id     INT PRIMARY KEY,
  server_gold INT DEFAULT 0,
  server_iron INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS hc_stats (
  id       INT AUTO_INCREMENT PRIMARY KEY,
  user_id  INT NOT NULL,
  gamemode VARCHAR(30) NOT NULL,
  kills    INT DEFAULT 0,
  deaths   INT DEFAULT 0,
  wins     INT DEFAULT 0,
  losses   INT DEFAULT 0,
  coins    INT DEFAULT 0,
  UNIQUE KEY uq (user_id, gamemode)
);

CREATE TABLE IF NOT EXISTS hc_inventory (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  user_id    INT NOT NULL,
  item_type  VARCHAR(30) DEFAULT 'rank',
  item_name  VARCHAR(80) NOT NULL,
  gamemode   VARCHAR(30) DEFAULT '',
  gifted_by  INT,
  status     VARCHAR(20) DEFAULT 'active',
  created_at DATETIME    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hc_gifts (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  from_user_id INT NOT NULL,
  to_username  VARCHAR(50) NOT NULL,
  item_type    VARCHAR(30) DEFAULT 'rank',
  item_name    VARCHAR(80) NOT NULL,
  gamemode     VARCHAR(30) DEFAULT '',
  status       VARCHAR(20) DEFAULT 'pending',
  created_at   DATETIME    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hc_cart (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  user_id    INT NOT NULL,
  item_id    VARCHAR(60) NOT NULL,
  item_name  VARCHAR(80) NOT NULL,
  item_price DOUBLE NOT NULL,
  gamemode   VARCHAR(30) DEFAULT ''
);

CREATE TABLE IF NOT EXISTS hc_forums (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  title      VARCHAR(200) NOT NULL,
  content    TEXT NOT NULL,
  author_id  INT NOT NULL,
  category   VARCHAR(40) DEFAULT 'general',
  views      INT DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hc_replies (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  forum_id   INT NOT NULL,
  author_id  INT NOT NULL,
  content    TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hc_tickets (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  title       VARCHAR(200) NOT NULL,
  category    VARCHAR(40)  DEFAULT 'general',
  description TEXT         NOT NULL,
  author_id   INT          NOT NULL,
  status      VARCHAR(20)  DEFAULT 'open',
  created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hc_ticket_msgs (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  ticket_id  INT NOT NULL,
  author_id  INT NOT NULL,
  content    TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════
-- OPTIONAL: Create a dedicated MySQL user for the app
-- (more secure than using root)
-- ═══════════════════════════════════════════════════════
-- CREATE USER 'hellcore'@'localhost' IDENTIFIED BY 'StrongPassword123!';
-- GRANT ALL PRIVILEGES ON hellcore.* TO 'hellcore'@'localhost';
-- FLUSH PRIVILEGES;

SELECT 'Hellcore database setup complete!' AS status;
