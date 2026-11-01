import { CatalogControls } from "./catalog-controls.js";
import { MaterialsCatalog } from "./materials-catalog.js";
import { CourseNavigation } from "./course-navigation.js";
import { CourseShell } from "./course-shell.js";
import { MaterialPreview } from "./material-preview.js";

customElements.define("catalog-controls", CatalogControls);
customElements.define("materials-catalog", MaterialsCatalog);
customElements.define("course-navigation", CourseNavigation);
customElements.define("course-shell", CourseShell);
customElements.define("material-preview", MaterialPreview);

import { LectureViewer } from "./lecture-viewer.js";
customElements.define("lecture-viewer", LectureViewer);

import './handbook-quiz.js';
