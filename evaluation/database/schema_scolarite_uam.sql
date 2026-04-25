-- ============================================================================
-- SCHÉMA DE LA BASE DE DONNÉES DE SCOLARITÉ — UNIVERSITÉ ABDOU MOUMOUNI
-- ============================================================================
-- Version : 1.0 (simulation pour prototype chatbot)
-- SGBD cible : MySQL 8.0+
-- Encodage : UTF-8 (utf8mb4)
-- ============================================================================

CREATE DATABASE IF NOT EXISTS scolarite_uam
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE scolarite_uam;

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 1 : Composantes (facultés, écoles, instituts)
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE composantes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sigle VARCHAR(10) NOT NULL UNIQUE,
    nom_complet VARCHAR(200) NOT NULL,
    type_composante ENUM('faculte', 'ecole', 'institut') NOT NULL,
    doyen_directeur VARCHAR(150),
    email_contact VARCHAR(100),
    telephone VARCHAR(20),
    adresse TEXT,
    date_creation DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 2 : Départements
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE departements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    composante_id INT NOT NULL,
    nom VARCHAR(200) NOT NULL,
    chef_departement VARCHAR(150),
    FOREIGN KEY (composante_id) REFERENCES composantes(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 3 : Formations
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE formations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    departement_id INT NOT NULL,
    intitule VARCHAR(300) NOT NULL,
    niveau ENUM('L1', 'L2', 'L3', 'M1', 'M2', 'D1', 'D2', 'D3') NOT NULL,
    type_formation ENUM('initiale', 'continue', 'a_distance') DEFAULT 'initiale',
    capacite_accueil INT,
    duree_semestres INT DEFAULT 2,
    est_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (departement_id) REFERENCES departements(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 4 : Étudiants
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE etudiants (
    id INT AUTO_INCREMENT PRIMARY KEY,
    matricule VARCHAR(20) NOT NULL UNIQUE,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(150) NOT NULL,
    date_naissance DATE NOT NULL,
    lieu_naissance VARCHAR(100),
    sexe ENUM('M', 'F') NOT NULL,
    nationalite VARCHAR(50) DEFAULT 'Nigérienne',
    telephone VARCHAR(20),
    email VARCHAR(100),
    adresse_niamey TEXT,
    type_etudiant ENUM(
        'nouveau_bachelier', 'reinscription', 'transfert_interne',
        'transfert_externe', 'etudiant_etranger',
        'candidat_master', 'candidat_doctorat', 'professionnel'
    ) NOT NULL,
    annee_bac INT,
    serie_bac VARCHAR(10),
    mention_bac VARCHAR(20),
    etablissement_origine VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 5 : Inscriptions (une ligne par année académique par étudiant)
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE inscriptions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    etudiant_id INT NOT NULL,
    formation_id INT NOT NULL,
    annee_academique VARCHAR(9) NOT NULL,  -- ex: '2024-2025'
    date_inscription DATE,
    statut ENUM('en_attente', 'validee', 'rejetee', 'annulee') DEFAULT 'en_attente',
    numero_recu VARCHAR(30),
    observations TEXT,
    FOREIGN KEY (etudiant_id) REFERENCES etudiants(id) ON DELETE CASCADE,
    FOREIGN KEY (formation_id) REFERENCES formations(id) ON DELETE CASCADE,
    UNIQUE KEY uk_inscription (etudiant_id, formation_id, annee_academique)
) ENGINE=InnoDB;

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 6 : Paiements des frais
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE paiements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    inscription_id INT NOT NULL,
    type_frais ENUM(
        'inscription', 'scolarite', 'bibliotheque',
        'assurance', 'carte_etudiant', 'autre'
    ) NOT NULL,
    montant DECIMAL(10, 2) NOT NULL,
    date_paiement DATE NOT NULL,
    mode_paiement ENUM('especes', 'virement', 'mobile_money', 'cheque') DEFAULT 'especes',
    reference_paiement VARCHAR(50),
    FOREIGN KEY (inscription_id) REFERENCES inscriptions(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 7 : Unités d'enseignement
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE unites_enseignement (
    id INT AUTO_INCREMENT PRIMARY KEY,
    formation_id INT NOT NULL,
    code_ue VARCHAR(20) NOT NULL,
    intitule VARCHAR(200) NOT NULL,
    credits_ects INT NOT NULL DEFAULT 3,
    semestre INT NOT NULL,  -- 1 ou 2
    coefficient DECIMAL(3, 1) DEFAULT 1.0,
    type_ue ENUM('fondamentale', 'complementaire', 'optionnelle', 'transversale') DEFAULT 'fondamentale',
    FOREIGN KEY (formation_id) REFERENCES formations(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 8 : Résultats académiques
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE resultats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    inscription_id INT NOT NULL,
    ue_id INT NOT NULL,
    note_cc DECIMAL(4, 2),       -- Contrôle continu (sur 20)
    note_examen DECIMAL(4, 2),   -- Examen (sur 20)
    note_finale DECIMAL(4, 2),   -- Moyenne pondérée
    session ENUM('normale', 'rattrapage') DEFAULT 'normale',
    statut_ue ENUM('valide', 'non_valide', 'en_attente') DEFAULT 'en_attente',
    annee_academique VARCHAR(9),
    FOREIGN KEY (inscription_id) REFERENCES inscriptions(id) ON DELETE CASCADE,
    FOREIGN KEY (ue_id) REFERENCES unites_enseignement(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 9 : Documents délivrés
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE documents_delivres (
    id INT AUTO_INCREMENT PRIMARY KEY,
    etudiant_id INT NOT NULL,
    type_document ENUM(
        'carte_etudiant', 'attestation_inscription',
        'releve_notes', 'attestation_reussite',
        'diplome', 'certificat_scolarite'
    ) NOT NULL,
    date_demande DATE,
    date_delivrance DATE,
    statut ENUM('demande', 'en_cours', 'delivre', 'refuse') DEFAULT 'demande',
    FOREIGN KEY (etudiant_id) REFERENCES etudiants(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ────────────────────────────────────────────────────────────────────────────
-- VUES utiles pour le chatbot
-- ────────────────────────────────────────────────────────────────────────────

-- Vue : situation complète d'un étudiant
CREATE OR REPLACE VIEW vue_situation_etudiant AS
SELECT
    e.matricule,
    CONCAT(e.prenom, ' ', e.nom) AS nom_complet,
    e.type_etudiant,
    c.sigle AS composante,
    f.intitule AS formation,
    f.niveau,
    i.annee_academique,
    i.statut AS statut_inscription,
    i.date_inscription
FROM etudiants e
JOIN inscriptions i ON e.id = i.etudiant_id
JOIN formations f ON i.formation_id = f.id
JOIN departements d ON f.departement_id = d.id
JOIN composantes c ON d.composante_id = c.id;

-- Vue : état des paiements
CREATE OR REPLACE VIEW vue_paiements_etudiant AS
SELECT
    e.matricule,
    CONCAT(e.prenom, ' ', e.nom) AS nom_complet,
    i.annee_academique,
    p.type_frais,
    p.montant,
    p.date_paiement,
    p.mode_paiement
FROM etudiants e
JOIN inscriptions i ON e.id = i.etudiant_id
JOIN paiements p ON i.id = p.inscription_id;

-- Vue : résultats académiques
CREATE OR REPLACE VIEW vue_resultats_etudiant AS
SELECT
    e.matricule,
    CONCAT(e.prenom, ' ', e.nom) AS nom_complet,
    ue.code_ue,
    ue.intitule AS nom_ue,
    ue.credits_ects,
    r.note_cc,
    r.note_examen,
    r.note_finale,
    r.session,
    r.statut_ue,
    r.annee_academique
FROM etudiants e
JOIN inscriptions i ON e.id = i.etudiant_id
JOIN resultats r ON i.id = r.inscription_id
JOIN unites_enseignement ue ON r.ue_id = ue.id;
