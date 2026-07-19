# Directives et Règles pour les Agents IA (AGENTS.md)

Ce document définit les standards de qualité, de test et de validation obligatoires pour tous les agents intervenant sur ce dépôt.

---

## 1. Exécution des Tests

Avant de soumettre, commiter ou pousser tout changement, l'agent doit impérativement s'assurer que l'intégralité de la suite de tests passe localement.

* **Commande de test unitaire** :
  ```bash
  uv run pytest
  ```
* **Attente** : Les 25 tests unitaires (ou plus, si de nouveaux tests sont ajoutés) doivent tous être au statut **pass** (vert). Il est strictement interdit de commiter si des tests échouent.

---

## 2. Validation Visuelle Obligatoire (Streamlit)

Pour chaque implémentation, modification de code Python ou modification d'interface utilisateur, l'agent doit impérativement lancer et vérifier l'application Streamlit localement.

### Procédure de validation :
1. **Lancement de l'application en arrière-plan** :
   ```bash
   uv run streamlit run streamlit_app.py --server.port 8501 --server.headless true
   ```
2. **Navigation et Interaction via le Navigateur** :
   - L'agent doit utiliser l'intégration de navigation Chrome (via les outils MCP ou Playwright) pour ouvrir `http://localhost:8501`.
   - L'agent doit interagir avec l'application (par exemple, poser une question d'économie US via le chat) pour s'assurer que la chaîne complète (Streamlit ➔ Snowflake Cortex ➔ réponse) fonctionne sans erreur.
3. **Capture d'écran de preuve** :
   - Prenez une capture d'écran du navigateur montrant le rendu visuel de la page et la réponse générée.
   - Cette capture d'écran doit être incluse dans la réponse finale ou le walkthrough de validation pour prouver visuellement le bon fonctionnement.
4. **Nettoyage** :
   - Arrêtez le serveur Streamlit à la fin du test pour libérer le port réseau.

---

## 3. Preuve de fonctionnement (Walkthrough)

Toute tâche de développement doit se terminer par un résumé ou un document de walkthrough détaillant :
* La liste des changements effectués.
* La preuve d'exécution réussie de `pytest`.
* La preuve visuelle (logs et capture d'écran intégrée) montrant l'application Streamlit fonctionnelle en local.
* L'état du pipeline CI distant (GitHub Actions).

## 4. YAGNI (You Aren't Gonna Need It) : 
Utilise /ponytail skill

## 5. When reporting information to me :
Be extremely concise and sacrify grammar for the sake of concision.
