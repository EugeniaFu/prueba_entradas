CREATE DATABASE  IF NOT EXISTS `andamiosdb` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `andamiosdb`;
-- MySQL dump 10.13  Distrib 8.0.46, for Win64 (x86_64)
--
-- Host: localhost    Database: andamiosdb
-- ------------------------------------------------------
-- Server version	9.7.0

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
SET @MYSQLDUMP_TEMP_LOG_BIN = @@SESSION.SQL_LOG_BIN;
SET @@SESSION.SQL_LOG_BIN= 0;

--
-- GTID state at the beginning of the backup 
--

SET @@GLOBAL.GTID_PURGED=/*!80000 '+'*/ '03953f27-506f-11f1-b14f-b1df4ad23fc6:1-207';

--
-- Table structure for table `clientes`
--

DROP TABLE IF EXISTS `clientes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `clientes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `apellido1` varchar(100) NOT NULL,
  `apellido2` varchar(100) NOT NULL,
  `telefono` varchar(20) NOT NULL,
  `correo` varchar(100) DEFAULT NULL,
  `rfc` varchar(20) DEFAULT NULL,
  `tipo_cliente` varchar(20) NOT NULL,
  `sucursal_id` int DEFAULT NULL,
  `fecha_alta` datetime DEFAULT CURRENT_TIMESTAMP,
  `activo` tinyint(1) DEFAULT '1',
  `codigo_cliente` varchar(10) DEFAULT NULL,
  `rol_id` int DEFAULT NULL,
  `calle` varchar(255) DEFAULT NULL,
  `numero_exterior` varchar(10) DEFAULT NULL,
  `numero_interior` varchar(10) DEFAULT NULL,
  `colonia` varchar(100) DEFAULT NULL,
  `codigo_postal` varchar(5) DEFAULT NULL,
  `municipio` varchar(100) DEFAULT NULL,
  `estado` varchar(50) DEFAULT NULL,
  `entre_calles` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `codigo_cliente` (`codigo_cliente`),
  UNIQUE KEY `codigo_cliente_2` (`codigo_cliente`),
  KEY `fk_cliente_sucursal` (`sucursal_id`),
  KEY `rol_id` (`rol_id`),
  CONSTRAINT `clientes_ibfk_1` FOREIGN KEY (`rol_id`) REFERENCES `roles` (`id`),
  CONSTRAINT `fk_cliente_sucursal` FOREIGN KEY (`sucursal_id`) REFERENCES `sucursales` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cotizacion_detalle`
--

DROP TABLE IF EXISTS `cotizacion_detalle`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cotizacion_detalle` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cotizacion_id` int NOT NULL,
  `producto_id` int NOT NULL,
  `cantidad` int NOT NULL,
  `precio_unitario` decimal(10,2) NOT NULL,
  `subtotal` decimal(10,2) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `producto_id` (`producto_id`),
  KEY `idx_cotizacion_detalle_cotizacion` (`cotizacion_id`),
  CONSTRAINT `cotizacion_detalle_ibfk_1` FOREIGN KEY (`cotizacion_id`) REFERENCES `cotizaciones` (`id`) ON DELETE CASCADE,
  CONSTRAINT `cotizacion_detalle_ibfk_2` FOREIGN KEY (`producto_id`) REFERENCES `productos` (`id_producto`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cotizacion_seguimiento`
--

DROP TABLE IF EXISTS `cotizacion_seguimiento`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cotizacion_seguimiento` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cotizacion_id` int NOT NULL,
  `estado_anterior` varchar(50) DEFAULT NULL,
  `estado_nuevo` varchar(50) NOT NULL,
  `comentarios` text,
  `fecha_cambio` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `usuario_id` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `cotizacion_id` (`cotizacion_id`),
  KEY `usuario_id` (`usuario_id`),
  CONSTRAINT `cotizacion_seguimiento_ibfk_1` FOREIGN KEY (`cotizacion_id`) REFERENCES `cotizaciones` (`id`) ON DELETE CASCADE,
  CONSTRAINT `cotizacion_seguimiento_ibfk_2` FOREIGN KEY (`usuario_id`) REFERENCES `usuarios` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cotizaciones`
--

DROP TABLE IF EXISTS `cotizaciones`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cotizaciones` (
  `id` int NOT NULL AUTO_INCREMENT,
  `numero_cotizacion` varchar(20) NOT NULL,
  `cliente_nombre` varchar(100) NOT NULL,
  `cliente_telefono` varchar(20) NOT NULL,
  `cliente_email` varchar(100) DEFAULT NULL,
  `cliente_empresa` varchar(100) DEFAULT NULL,
  `dias_renta` int NOT NULL,
  `requiere_traslado` tinyint(1) DEFAULT '0',
  `tipo_traslado` enum('medio','redondo') DEFAULT NULL,
  `costo_traslado` decimal(10,2) DEFAULT '0.00',
  `subtotal` decimal(10,2) NOT NULL DEFAULT '0.00',
  `iva` decimal(10,2) NOT NULL DEFAULT '0.00',
  `total` decimal(10,2) NOT NULL DEFAULT '0.00',
  `estado` enum('enviada','vencida','renta') DEFAULT 'enviada',
  `fecha_creacion` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `fecha_vigencia` date NOT NULL,
  `usuario_id` int NOT NULL,
  `sucursal_id` int NOT NULL,
  `observaciones` text,
  PRIMARY KEY (`id`),
  UNIQUE KEY `numero_cotizacion` (`numero_cotizacion`),
  KEY `usuario_id` (`usuario_id`),
  KEY `idx_cotizaciones_numero` (`numero_cotizacion`),
  KEY `idx_cotizaciones_estado` (`estado`),
  KEY `idx_cotizaciones_fecha` (`fecha_creacion`),
  KEY `idx_cotizaciones_sucursal` (`sucursal_id`),
  CONSTRAINT `cotizaciones_ibfk_1` FOREIGN KEY (`usuario_id`) REFERENCES `usuarios` (`id`),
  CONSTRAINT `cotizaciones_ibfk_2` FOREIGN KEY (`sucursal_id`) REFERENCES `sucursales` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `dashboard_notas`
--

DROP TABLE IF EXISTS `dashboard_notas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dashboard_notas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nota` text NOT NULL,
  `usuario_id` int DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `sucursal_id` int DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `documentos_cliente`
--

DROP TABLE IF EXISTS `documentos_cliente`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `documentos_cliente` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cliente_id` int NOT NULL,
  `tipo_documento` varchar(30) NOT NULL,
  `archivo` varchar(255) NOT NULL,
  `fecha_subida` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `cliente_id` (`cliente_id`),
  CONSTRAINT `documentos_cliente_ibfk_1` FOREIGN KEY (`cliente_id`) REFERENCES `clientes` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=42 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `historial_rentas`
--

DROP TABLE IF EXISTS `historial_rentas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `historial_rentas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `renta_id` int DEFAULT NULL,
  `accion` varchar(50) DEFAULT NULL,
  `descripcion` text,
  `fecha` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `renta_id` (`renta_id`),
  CONSTRAINT `historial_rentas_ibfk_1` FOREIGN KEY (`renta_id`) REFERENCES `rentas` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `inventario_sucursal`
--

DROP TABLE IF EXISTS `inventario_sucursal`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `inventario_sucursal` (
  `id_inventario` int NOT NULL AUTO_INCREMENT,
  `id_sucursal` int NOT NULL,
  `id_pieza` int NOT NULL,
  `total` int NOT NULL DEFAULT '0',
  `disponibles` int NOT NULL DEFAULT '0',
  `rentadas` int NOT NULL DEFAULT '0',
  `daniadas` int NOT NULL DEFAULT '0',
  `en_reparacion` int NOT NULL DEFAULT '0',
  `stock_minimo` int NOT NULL DEFAULT '0',
  `perdidas` int DEFAULT '0',
  PRIMARY KEY (`id_inventario`),
  UNIQUE KEY `id_sucursal_2` (`id_sucursal`,`id_pieza`),
  KEY `id_sucursal` (`id_sucursal`),
  KEY `id_pieza` (`id_pieza`),
  CONSTRAINT `inventario_sucursal_ibfk_1` FOREIGN KEY (`id_sucursal`) REFERENCES `sucursales` (`id`),
  CONSTRAINT `inventario_sucursal_ibfk_2` FOREIGN KEY (`id_pieza`) REFERENCES `piezas` (`id_pieza`)
) ENGINE=InnoDB AUTO_INCREMENT=88 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `movimientos_caja`
--

DROP TABLE IF EXISTS `movimientos_caja`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `movimientos_caja` (
  `id` int NOT NULL AUTO_INCREMENT,
  `fecha_hora` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `tipo` enum('ingreso','egreso') NOT NULL,
  `concepto` varchar(255) NOT NULL,
  `monto` decimal(10,2) NOT NULL,
  `metodo_pago` enum('EFECTIVO','T.DÉBITO','T.CRÉDITO','TRANSFERENCIA') NOT NULL,
  `numero_seguimiento` varchar(100) DEFAULT NULL,
  `observaciones` text,
  `tipo_movimiento` enum('manual','automatico') NOT NULL DEFAULT 'manual',
  `referencia_tabla` varchar(50) DEFAULT NULL COMMENT 'prefacturas, notas_cobro_extra, notas_cobro_retraso',
  `referencia_id` int DEFAULT NULL COMMENT 'ID del registro que generó este movimiento',
  `usuario_id` int NOT NULL,
  `sucursal_id` int NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_tipo` (`tipo`),
  KEY `idx_referencia` (`referencia_tabla`,`referencia_id`),
  KEY `idx_tipo_movimiento` (`tipo_movimiento`),
  KEY `usuario_id` (`usuario_id`),
  KEY `idx_fecha_hora` (`fecha_hora`),
  KEY `idx_sucursal_fecha_hora` (`sucursal_id`,`fecha_hora`),
  CONSTRAINT `movimientos_caja_ibfk_1` FOREIGN KEY (`usuario_id`) REFERENCES `usuarios` (`id`),
  CONSTRAINT `movimientos_caja_ibfk_2` FOREIGN KEY (`sucursal_id`) REFERENCES `sucursales` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=20 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `movimientos_inventario`
--

DROP TABLE IF EXISTS `movimientos_inventario`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `movimientos_inventario` (
  `id_movimiento` int NOT NULL AUTO_INCREMENT,
  `id_sucursal` int NOT NULL,
  `id_pieza` int NOT NULL,
  `tipo_movimiento` varchar(50) NOT NULL,
  `cantidad` int NOT NULL,
  `fecha` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `usuario` int DEFAULT NULL,
  `sucursal_destino` int DEFAULT NULL,
  `observaciones` text,
  `folio_nota_salida` varchar(10) DEFAULT NULL,
  `folio_nota_entrada` varchar(10) DEFAULT NULL,
  `descripcion` text,
  PRIMARY KEY (`id_movimiento`),
  KEY `id_sucursal` (`id_sucursal`),
  KEY `id_pieza` (`id_pieza`),
  KEY `sucursal_destino` (`sucursal_destino`),
  KEY `fk_usuario` (`usuario`),
  CONSTRAINT `fk_usuario` FOREIGN KEY (`usuario`) REFERENCES `usuarios` (`id`),
  CONSTRAINT `movimientos_inventario_ibfk_1` FOREIGN KEY (`id_sucursal`) REFERENCES `sucursales` (`id`),
  CONSTRAINT `movimientos_inventario_ibfk_2` FOREIGN KEY (`id_pieza`) REFERENCES `piezas` (`id_pieza`),
  CONSTRAINT `movimientos_inventario_ibfk_3` FOREIGN KEY (`sucursal_destino`) REFERENCES `sucursales` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=49 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `notas_cobro_extra`
--

DROP TABLE IF EXISTS `notas_cobro_extra`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notas_cobro_extra` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nota_entrada_id` int NOT NULL,
  `tipo` varchar(20) DEFAULT NULL,
  `subtotal` decimal(10,2) NOT NULL DEFAULT '0.00',
  `iva` decimal(10,2) NOT NULL DEFAULT '0.00',
  `total` decimal(10,2) NOT NULL DEFAULT '0.00',
  `metodo_pago` varchar(20) DEFAULT NULL,
  `monto_recibido` decimal(10,2) DEFAULT NULL,
  `cambio` decimal(10,2) DEFAULT NULL,
  `fecha` datetime DEFAULT CURRENT_TIMESTAMP,
  `facturable` tinyint(1) DEFAULT '0',
  `numero_seguimiento` varchar(50) DEFAULT NULL,
  `observaciones` text,
  `estado_pago` varchar(20) NOT NULL DEFAULT 'Extra Pendiente',
  `folio` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `nota_entrada_id` (`nota_entrada_id`),
  CONSTRAINT `notas_cobro_extra_ibfk_1` FOREIGN KEY (`nota_entrada_id`) REFERENCES `notas_entrada` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `notas_cobro_extra_detalle`
--

DROP TABLE IF EXISTS `notas_cobro_extra_detalle`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notas_cobro_extra_detalle` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cobro_extra_id` int NOT NULL,
  `id_pieza` int DEFAULT NULL,
  `tipo_afectacion` varchar(20) DEFAULT NULL,
  `cantidad` int NOT NULL DEFAULT '0',
  `costo_unitario` decimal(10,2) NOT NULL DEFAULT '0.00',
  `subtotal` decimal(10,2) NOT NULL DEFAULT '0.00',
  PRIMARY KEY (`id`),
  KEY `cobro_extra_id` (`cobro_extra_id`),
  KEY `id_pieza` (`id_pieza`),
  CONSTRAINT `notas_cobro_extra_detalle_ibfk_1` FOREIGN KEY (`cobro_extra_id`) REFERENCES `notas_cobro_extra` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `notas_cobro_extra_detalle_ibfk_2` FOREIGN KEY (`id_pieza`) REFERENCES `piezas` (`id_pieza`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `notas_cobro_retraso`
--

DROP TABLE IF EXISTS `notas_cobro_retraso`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notas_cobro_retraso` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nota_entrada_id` int NOT NULL,
  `fecha` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `subtotal` decimal(10,2) NOT NULL,
  `iva` decimal(10,2) NOT NULL,
  `total` decimal(10,2) NOT NULL,
  `metodo_pago` varchar(50) DEFAULT NULL,
  `monto_recibido` decimal(10,2) DEFAULT NULL,
  `cambio` decimal(10,2) DEFAULT NULL,
  `observaciones` text,
  `facturable` tinyint(1) DEFAULT '0',
  `traslado_extra` varchar(50) DEFAULT NULL,
  `costo_traslado_extra` decimal(10,2) DEFAULT '0.00',
  `estado_pago` varchar(30) DEFAULT 'Retraso Pendiente',
  `numero_seguimiento` varchar(50) DEFAULT NULL,
  `folio` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `nota_entrada_id` (`nota_entrada_id`),
  CONSTRAINT `notas_cobro_retraso_ibfk_1` FOREIGN KEY (`nota_entrada_id`) REFERENCES `notas_entrada` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `notas_cobro_retraso_detalle`
--

DROP TABLE IF EXISTS `notas_cobro_retraso_detalle`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notas_cobro_retraso_detalle` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cobro_retraso_id` int NOT NULL,
  `id_producto` int NOT NULL,
  `nombre_producto` varchar(100) DEFAULT NULL,
  `cantidad` int NOT NULL,
  `precio_unitario` decimal(10,2) NOT NULL,
  `dias_retraso` int NOT NULL,
  `subtotal` decimal(10,2) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `cobro_retraso_id` (`cobro_retraso_id`),
  KEY `id_producto` (`id_producto`),
  CONSTRAINT `notas_cobro_retraso_detalle_ibfk_1` FOREIGN KEY (`cobro_retraso_id`) REFERENCES `notas_cobro_retraso` (`id`),
  CONSTRAINT `notas_cobro_retraso_detalle_ibfk_2` FOREIGN KEY (`id_producto`) REFERENCES `productos` (`id_producto`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `notas_entrada`
--

DROP TABLE IF EXISTS `notas_entrada`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notas_entrada` (
  `id` int NOT NULL AUTO_INCREMENT,
  `folio` int NOT NULL,
  `renta_id` int NOT NULL,
  `nota_salida_id` int NOT NULL,
  `fecha_entrada_real` datetime DEFAULT CURRENT_TIMESTAMP,
  `requiere_traslado_extra` enum('ninguno','medio','redondo') DEFAULT 'ninguno',
  `costo_traslado_extra` decimal(10,2) DEFAULT '0.00',
  `observaciones` text,
  `estado` enum('normal','con_extras') DEFAULT 'normal',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `estado_retraso` varchar(30) DEFAULT 'Sin Retraso',
  `accion_devolucion` varchar(20) NOT NULL DEFAULT 'no',
  PRIMARY KEY (`id`),
  KEY `nota_salida_id` (`nota_salida_id`),
  KEY `idx_renta` (`renta_id`),
  CONSTRAINT `notas_entrada_ibfk_1` FOREIGN KEY (`renta_id`) REFERENCES `rentas` (`id`),
  CONSTRAINT `notas_entrada_ibfk_2` FOREIGN KEY (`nota_salida_id`) REFERENCES `notas_salida` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=47 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `notas_entrada_detalle`
--

DROP TABLE IF EXISTS `notas_entrada_detalle`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notas_entrada_detalle` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nota_entrada_id` int NOT NULL,
  `id_pieza` int NOT NULL,
  `cantidad_esperada` int NOT NULL,
  `cantidad_recibida` int DEFAULT NULL,
  `cantidad_buena` int DEFAULT '0',
  `cantidad_danada` int DEFAULT '0',
  `cantidad_sucia` int DEFAULT '0',
  `cantidad_perdida` int DEFAULT '0',
  `observaciones_pieza` text,
  PRIMARY KEY (`id`),
  KEY `id_pieza` (`id_pieza`),
  KEY `idx_nota_entrada` (`nota_entrada_id`),
  CONSTRAINT `notas_entrada_detalle_ibfk_1` FOREIGN KEY (`nota_entrada_id`) REFERENCES `notas_entrada` (`id`) ON DELETE CASCADE,
  CONSTRAINT `notas_entrada_detalle_ibfk_2` FOREIGN KEY (`id_pieza`) REFERENCES `piezas` (`id_pieza`)
) ENGINE=InnoDB AUTO_INCREMENT=103 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `notas_salida`
--

DROP TABLE IF EXISTS `notas_salida`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notas_salida` (
  `id` int NOT NULL AUTO_INCREMENT,
  `folio` int NOT NULL,
  `numero_referencia` varchar(100) DEFAULT NULL,
  `renta_id` int NOT NULL,
  `fecha` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `observaciones` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `renta_id` (`renta_id`),
  CONSTRAINT `notas_salida_ibfk_1` FOREIGN KEY (`renta_id`) REFERENCES `rentas` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=46 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `notas_salida_detalle`
--

DROP TABLE IF EXISTS `notas_salida_detalle`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notas_salida_detalle` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nota_salida_id` int NOT NULL,
  `id_pieza` int NOT NULL,
  `cantidad` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `nota_salida_id` (`nota_salida_id`),
  KEY `id_pieza` (`id_pieza`),
  CONSTRAINT `notas_salida_detalle_ibfk_1` FOREIGN KEY (`nota_salida_id`) REFERENCES `notas_salida` (`id`),
  CONSTRAINT `notas_salida_detalle_ibfk_2` FOREIGN KEY (`id_pieza`) REFERENCES `piezas` (`id_pieza`)
) ENGINE=InnoDB AUTO_INCREMENT=100 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `password_reset_tokens`
--

DROP TABLE IF EXISTS `password_reset_tokens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `password_reset_tokens` (
  `id` int NOT NULL AUTO_INCREMENT,
  `usuario_id` int NOT NULL,
  `token` varchar(128) NOT NULL,
  `expires_at` datetime NOT NULL,
  `usado` tinyint(1) DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `usuario_id` (`usuario_id`),
  CONSTRAINT `password_reset_tokens_ibfk_1` FOREIGN KEY (`usuario_id`) REFERENCES `usuarios` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `permisos`
--

DROP TABLE IF EXISTS `permisos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `permisos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nombre` varchar(50) NOT NULL,
  `descripcion` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `nombre` (`nombre`)
) ENGINE=InnoDB AUTO_INCREMENT=57 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `piezas`
--

DROP TABLE IF EXISTS `piezas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `piezas` (
  `id_pieza` int NOT NULL AUTO_INCREMENT,
  `nombre_pieza` varchar(100) NOT NULL,
  `categoria` varchar(100) DEFAULT NULL,
  `descripcion` text,
  `codigo_pieza` varchar(20) DEFAULT NULL,
  `estatus` varchar(20) DEFAULT 'activo',
  PRIMARY KEY (`id_pieza`),
  UNIQUE KEY `codigo_pieza` (`codigo_pieza`)
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `prefacturas`
--

DROP TABLE IF EXISTS `prefacturas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `prefacturas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `renta_id` int NOT NULL,
  `fecha_emision` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `generada` tinyint(1) DEFAULT '0',
  `tipo` enum('inicial','servicio','recargo','renovacion','abono') DEFAULT 'inicial',
  `pagada` tinyint(1) DEFAULT '0',
  `metodo_pago` enum('EFECTIVO','T.DÉBITO','T.CRÉDITO','TRANSFERENCIA') DEFAULT NULL,
  `monto` decimal(10,2) DEFAULT '0.00',
  `monto_recibido` decimal(10,2) DEFAULT NULL,
  `cambio` decimal(10,2) DEFAULT NULL,
  `numero_seguimiento` varchar(100) DEFAULT NULL,
  `observaciones` text,
  `facturable` tinyint(1) NOT NULL DEFAULT '1',
  `folio` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `renta_id` (`renta_id`),
  CONSTRAINT `prefacturas_ibfk_1` FOREIGN KEY (`renta_id`) REFERENCES `rentas` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=24 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `producto_piezas`
--

DROP TABLE IF EXISTS `producto_piezas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `producto_piezas` (
  `id_producto` int NOT NULL,
  `id_pieza` int NOT NULL,
  `cantidad` int NOT NULL,
  PRIMARY KEY (`id_producto`,`id_pieza`),
  KEY `id_pieza` (`id_pieza`),
  CONSTRAINT `producto_piezas_ibfk_1` FOREIGN KEY (`id_producto`) REFERENCES `productos` (`id_producto`),
  CONSTRAINT `producto_piezas_ibfk_2` FOREIGN KEY (`id_pieza`) REFERENCES `piezas` (`id_pieza`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `producto_precios`
--

DROP TABLE IF EXISTS `producto_precios`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `producto_precios` (
  `id_producto` int NOT NULL,
  `precio_dia` decimal(10,2) DEFAULT NULL,
  `precio_14_dias` decimal(10,2) DEFAULT NULL,
  `precio_29_dias` decimal(10,2) DEFAULT NULL,
  `precio_30_dias` decimal(10,2) DEFAULT NULL,
  PRIMARY KEY (`id_producto`),
  CONSTRAINT `producto_precios_ibfk_1` FOREIGN KEY (`id_producto`) REFERENCES `productos` (`id_producto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `productos`
--

DROP TABLE IF EXISTS `productos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `productos` (
  `id_producto` int NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `descripcion` text,
  `tipo` enum('conjunto','individual') NOT NULL,
  `estatus` enum('activo','descontinuado') DEFAULT 'activo',
  `precio_unico` tinyint(1) DEFAULT '0',
  PRIMARY KEY (`id_producto`)
) ENGINE=InnoDB AUTO_INCREMENT=15 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `renta_detalle`
--

DROP TABLE IF EXISTS `renta_detalle`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `renta_detalle` (
  `id` int NOT NULL AUTO_INCREMENT,
  `renta_id` int DEFAULT NULL,
  `id_producto` int NOT NULL,
  `cantidad` int NOT NULL,
  `dias_renta` int DEFAULT NULL,
  `costo_unitario` decimal(10,2) DEFAULT NULL,
  `subtotal` decimal(10,2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `renta_id` (`renta_id`),
  KEY `id_producto` (`id_producto`),
  CONSTRAINT `renta_detalle_ibfk_1` FOREIGN KEY (`renta_id`) REFERENCES `rentas` (`id`) ON DELETE CASCADE,
  CONSTRAINT `renta_detalle_ibfk_2` FOREIGN KEY (`id_producto`) REFERENCES `productos` (`id_producto`)
) ENGINE=InnoDB AUTO_INCREMENT=106 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `rentas`
--

DROP TABLE IF EXISTS `rentas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `rentas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cliente_id` int NOT NULL,
  `id_sucursal` int DEFAULT NULL,
  `fecha_registro` datetime DEFAULT CURRENT_TIMESTAMP,
  `fecha_salida` date DEFAULT NULL,
  `fecha_entrada` date DEFAULT NULL,
  `direccion_obra` text,
  `estado_renta` varchar(20) DEFAULT 'activa',
  `estado_pago` varchar(20) DEFAULT 'pendiente',
  `estado_cobro_extra` varchar(20) DEFAULT NULL,
  `total` decimal(10,2) DEFAULT '0.00',
  `iva` decimal(10,2) DEFAULT '0.00',
  `total_con_iva` decimal(10,2) DEFAULT '0.00',
  `observaciones` text,
  `fecha_programada` date DEFAULT NULL,
  `costo_traslado` decimal(10,2) DEFAULT '0.00',
  `traslado` varchar(100) DEFAULT NULL,
  `metodo_pago` varchar(55) DEFAULT NULL,
  `renta_asociada_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `cliente_id` (`cliente_id`),
  KEY `fk_rentas_sucursal` (`id_sucursal`),
  CONSTRAINT `fk_rentas_sucursal` FOREIGN KEY (`id_sucursal`) REFERENCES `sucursales` (`id`),
  CONSTRAINT `rentas_ibfk_1` FOREIGN KEY (`cliente_id`) REFERENCES `clientes` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=89 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `rentas_pendientes`
--

DROP TABLE IF EXISTS `rentas_pendientes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `rentas_pendientes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `renta_id` int NOT NULL,
  `id_producto` int NOT NULL,
  `id_pieza` int NOT NULL,
  `cantidad_pendiente` int NOT NULL,
  `fecha_registro` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `estado` varchar(30) DEFAULT 'pendiente',
  `renta_renovacion_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `renta_id` (`renta_id`),
  KEY `id_producto` (`id_producto`),
  KEY `id_pieza` (`id_pieza`),
  KEY `renta_renovacion_id` (`renta_renovacion_id`),
  CONSTRAINT `rentas_pendientes_ibfk_1` FOREIGN KEY (`renta_id`) REFERENCES `rentas` (`id`),
  CONSTRAINT `rentas_pendientes_ibfk_2` FOREIGN KEY (`id_producto`) REFERENCES `productos` (`id_producto`),
  CONSTRAINT `rentas_pendientes_ibfk_3` FOREIGN KEY (`id_pieza`) REFERENCES `piezas` (`id_pieza`),
  CONSTRAINT `rentas_pendientes_ibfk_4` FOREIGN KEY (`renta_renovacion_id`) REFERENCES `rentas` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `roles`
--

DROP TABLE IF EXISTS `roles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `roles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nombre` varchar(50) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `roles_permisos`
--

DROP TABLE IF EXISTS `roles_permisos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `roles_permisos` (
  `rol_id` int NOT NULL,
  `permiso_id` int NOT NULL,
  `permitido` tinyint(1) DEFAULT '1',
  PRIMARY KEY (`rol_id`,`permiso_id`),
  KEY `permiso_id` (`permiso_id`),
  CONSTRAINT `roles_permisos_ibfk_1` FOREIGN KEY (`rol_id`) REFERENCES `roles` (`id`),
  CONSTRAINT `roles_permisos_ibfk_2` FOREIGN KEY (`permiso_id`) REFERENCES `permisos` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `salidas_internas`
--

DROP TABLE IF EXISTS `salidas_internas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `salidas_internas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `id_sucursal` int NOT NULL,
  `folio_sucursal` int NOT NULL,
  `fecha_salida` datetime NOT NULL,
  `responsable_entrega` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Nombre del chofer o persona que se lleva el equipo',
  `observaciones` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `estado` enum('activa','finalizada_regreso','finalizada_no_regreso','cancelada') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'activa',
  `fecha_finalizacion` datetime DEFAULT NULL,
  `observaciones_finalizacion` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `usuario_creacion` int NOT NULL,
  `usuario_finalizacion` int DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_folio_sucursal` (`id_sucursal`,`folio_sucursal`),
  KEY `idx_sucursal` (`id_sucursal`),
  KEY `idx_folio_sucursal` (`folio_sucursal`),
  KEY `idx_estado` (`estado`),
  KEY `idx_fecha_salida` (`fecha_salida`),
  KEY `fk_salidas_internas_usuario_creacion` (`usuario_creacion`),
  KEY `fk_salidas_internas_usuario_finalizacion` (`usuario_finalizacion`),
  CONSTRAINT `fk_salidas_internas_sucursal` FOREIGN KEY (`id_sucursal`) REFERENCES `sucursales` (`id`),
  CONSTRAINT `fk_salidas_internas_usuario_creacion` FOREIGN KEY (`usuario_creacion`) REFERENCES `usuarios` (`id`),
  CONSTRAINT `fk_salidas_internas_usuario_finalizacion` FOREIGN KEY (`usuario_finalizacion`) REFERENCES `usuarios` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Tabla para registrar salidas internas de equipo (préstamos sin pago)';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `salidas_internas_detalle`
--

DROP TABLE IF EXISTS `salidas_internas_detalle`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `salidas_internas_detalle` (
  `id` int NOT NULL AUTO_INCREMENT,
  `salida_interna_id` int NOT NULL,
  `id_pieza` int NOT NULL,
  `cantidad` int NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_salida_interna` (`salida_interna_id`),
  KEY `idx_pieza` (`id_pieza`),
  CONSTRAINT `fk_salidas_internas_detalle_pieza` FOREIGN KEY (`id_pieza`) REFERENCES `piezas` (`id_pieza`),
  CONSTRAINT `fk_salidas_internas_detalle_salida` FOREIGN KEY (`salida_interna_id`) REFERENCES `salidas_internas` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Detalle de productos en cada salida interna';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `sucursales`
--

DROP TABLE IF EXISTS `sucursales`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sucursales` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `direccion` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `usuarios`
--

DROP TABLE IF EXISTS `usuarios`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `usuarios` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `apellido1` varchar(100) NOT NULL,
  `apellido2` varchar(100) NOT NULL,
  `correo` varchar(100) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `requiere_cambio_password` tinyint(1) DEFAULT '1',
  `estado` enum('activo','inactivo') DEFAULT 'activo',
  `rol_id` int NOT NULL,
  `sucursal_id` int DEFAULT NULL,
  `foto_url` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `usuario` (`correo`),
  KEY `fk_usuarios_roles` (`rol_id`),
  KEY `fk_usuarios_sucursales` (`sucursal_id`),
  CONSTRAINT `fk_usuarios_roles` FOREIGN KEY (`rol_id`) REFERENCES `roles` (`id`),
  CONSTRAINT `fk_usuarios_sucursales` FOREIGN KEY (`sucursal_id`) REFERENCES `sucursales` (`id`),
  CONSTRAINT `usuarios_ibfk_1` FOREIGN KEY (`rol_id`) REFERENCES `roles` (`id`),
  CONSTRAINT `usuarios_ibfk_2` FOREIGN KEY (`sucursal_id`) REFERENCES `sucursales` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `usuarios_permisos`
--

DROP TABLE IF EXISTS `usuarios_permisos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `usuarios_permisos` (
  `usuario_id` int NOT NULL,
  `permiso_id` int NOT NULL,
  `permitido` tinyint(1) DEFAULT '1',
  PRIMARY KEY (`usuario_id`,`permiso_id`),
  KEY `permiso_id` (`permiso_id`),
  CONSTRAINT `usuarios_permisos_ibfk_1` FOREIGN KEY (`usuario_id`) REFERENCES `usuarios` (`id`),
  CONSTRAINT `usuarios_permisos_ibfk_2` FOREIGN KEY (`permiso_id`) REFERENCES `permisos` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
SET @@SESSION.SQL_LOG_BIN = @MYSQLDUMP_TEMP_LOG_BIN;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-05-15 16:31:25
