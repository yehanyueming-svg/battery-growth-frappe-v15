module.exports = {
	env: {
		browser: true,
		es2021: true,
	},
	parserOptions: {
		ecmaVersion: "latest",
	},
	extends: ["eslint:recommended"],
	globals: {
		frappe: "readonly",
		__: "readonly",
		$: "readonly",
	},
};
