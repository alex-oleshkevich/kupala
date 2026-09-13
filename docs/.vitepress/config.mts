import { defineConfig } from "vitepress";

export default defineConfig({
	title: "Kupala",
	description: "An async full-stack Python framework for explicit, typed applications.",
	themeConfig: {
		nav: [
			{ text: "Motivation", link: "/motivation" },
			{ text: "Quick Start", link: "/quick-start" },
			{ text: "Tutorial", link: "/tutorial/" },
			{ text: "Components", link: "/components/" },
			{ text: "Advanced", link: "/advanced/" },
		],

		sidebar: {
			"/tutorial/": [
				{
					text: "Tutorial",
					items: [
						{ text: "Index", link: "/tutorial/" },
						{ text: "Project Setup", link: "/tutorial/project-setup" },
						{ text: "Applications", link: "/tutorial/applications" },
						{ text: "Routing", link: "/tutorial/routing" },
						{ text: "Requests", link: "/tutorial/requests" },
						{ text: "Responses", link: "/tutorial/responses" },
						{ text: "Dependency Injection", link: "/tutorial/dependency-injection" },
						{ text: "Templates", link: "/tutorial/templates" },
						{ text: "Middleware", link: "/tutorial/middleware" },
						{ text: "Errors", link: "/tutorial/errors" },
						{ text: "Security", link: "/tutorial/security" },
						{ text: "OpenAPI", link: "/tutorial/openapi" },
						{ text: "WebSockets and SSE", link: "/tutorial/websockets-and-sse" },
						{ text: "Commands", link: "/tutorial/commands" },
						{ text: "Extensions", link: "/tutorial/extensions" },
						{ text: "Testing", link: "/tutorial/testing" },
					],
				},
			],
			"/components/": [
				{
					text: "Components",
					items: [
						{ text: "Index", link: "/components/" },
						{ text: "Application", link: "/components/application" },
						{ text: "Routing", link: "/components/routing" },
						{ text: "Requests", link: "/components/requests" },
						{ text: "Request Binding", link: "/components/request-binding" },
						{ text: "Responses", link: "/components/responses" },
						{ text: "Dependencies", link: "/components/dependencies" },
						{ text: "Templates", link: "/components/templates" },
						{ text: "Middleware", link: "/components/middleware" },
						{ text: "Errors", link: "/components/errors" },
						{ text: "Security", link: "/components/security" },
						{ text: "WebSockets", link: "/components/websockets" },
						{ text: "Commands and CLI", link: "/components/commands-and-cli" },
						{ text: "API and OpenAPI", link: "/components/api-and-openapi" },
						{ text: "Extensions", link: "/components/extensions" },
						{ text: "Testing", link: "/components/testing" },
						{ text: "Generator", link: "/components/generator" },
					],
				},
			],
			"/advanced/": [
				{
					text: "Advanced",
					items: [
						{ text: "Index", link: "/advanced/" },
						{ text: "Architecture", link: "/advanced/architecture" },
						{ text: "Dependency Scopes", link: "/advanced/dependency-scopes" },
						{ text: "Routing Composition", link: "/advanced/routing-composition" },
						{ text: "Middleware Ordering", link: "/advanced/middleware-ordering" },
						{ text: "Lifespan and Cancellation", link: "/advanced/lifespan-and-cancellation" },
						{ text: "Starlette and ASGI", link: "/advanced/starlette-and-asgi" },
						{ text: "Security Boundaries", link: "/advanced/security-boundaries" },
						{ text: "Custom Extensions", link: "/advanced/custom-extensions" },
						{ text: "Custom OpenAPI", link: "/advanced/custom-openapi" },
					],
				},
			],
			"/": [
				{
					text: "About Kupala",
					items: [
						{ text: "Home", link: "/" },
						{ text: "Motivation", link: "/motivation" },
						{ text: "Quick Start", link: "/quick-start" },
					],
				},
			],
		},

		socialLinks: [
			{ icon: "github", link: "https://github.com/alex-oleshkevich/kupala" },
		],
	},
});
