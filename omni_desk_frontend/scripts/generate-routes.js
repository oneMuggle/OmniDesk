const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const fs = require('fs');
const path = require('path');

// Make paths relative to the script file to avoid issues with CWD
const routesFilePath = path.resolve(__dirname, '../src/routes/index.jsx');
const outputFilePath = path.resolve(__dirname, '../public/routes.json');

const code = fs.readFileSync(routesFilePath, 'utf-8');

const ast = parser.parse(code, {
  sourceType: 'module',
  plugins: ['jsx'],
});

const protectedRoutes = [];

function getAttributeValue(attributes, attrName) {
    const attr = attributes.find(a => a.name && a.name.name === attrName);
    if (!attr) return null;
    if (attr.value.type === 'StringLiteral') {
        return attr.value.value;
    }
    return null;
}

function getComponentName(element) {
    const name = element?.openingElement?.name;
    if (!name) return 'UnknownComponent';
    if (name.type === 'JSXIdentifier') return name.name;
    if (name.type === 'JSXMemberExpression') {
        return `${name.object.name}.${name.property.name}`;
    }
    return 'UnknownComponent';
}

function normalizeRoutePath(routePath) {
    if (!routePath) return '/';
    return routePath.startsWith('/') ? routePath : `/${routePath}`;
}

function processRouteObject(routeObject, parentPath) {
    if (!routeObject || routeObject.type !== 'ObjectExpression') return;

    const pathProp = routeObject.properties.find(p => p.key.name === 'path');
    const indexProp = routeObject.properties.find(p => p.key.name === 'index');
    const elementProp = routeObject.properties.find(p => p.key.name === 'element');
    const childrenProp = routeObject.properties.find(p => p.key.name === 'children');

    let currentPath = parentPath;
    if (pathProp && pathProp.value.type === 'StringLiteral') {
        currentPath = path.posix.join(parentPath, pathProp.value.value);
    }

    if (elementProp && elementProp.value.type === 'JSXElement') {
        const jsxElement = elementProp.value;
        const openingElement = jsxElement.openingElement;

        if (openingElement.name.name === 'ProtectedRoute') {
            const pageName = getAttributeValue(openingElement.attributes, 'pageName');
            const pagePath = getAttributeValue(openingElement.attributes, 'pagePath');
            const permissionsPath = getAttributeValue(openingElement.attributes, 'permissions');
            const componentChild = jsxElement.children.find(child => child.type === 'JSXElement');
            const actualRoutePath = normalizeRoutePath(
                indexProp?.value?.value === true ? parentPath : currentPath
            );
            const permissionPath = normalizeRoutePath(pagePath || permissionsPath || actualRoutePath);

            if ((pageName || pagePath || permissionsPath) && componentChild) {
                protectedRoutes.push({
                    name: pageName || permissionPath,
                    path: permissionPath,
                    component: getComponentName(componentChild),
                });
            }
        }
    }

    if (childrenProp && childrenProp.value.type === 'ArrayExpression') {
        childrenProp.value.elements.forEach(childRoute => {
            processRouteObject(childRoute, currentPath);
        });
    }
}


traverse(ast, {
  CallExpression(path) {
    if (path.node.callee.name === 'createBrowserRouter') {
      const routesArray = path.node.arguments[0];
      if (routesArray && routesArray.type === 'ArrayExpression') {
        routesArray.elements.forEach(routeObject => {
            processRouteObject(routeObject, '/');
        });
      }
    }
  },
});

// Remove duplicates
const uniqueRoutes = protectedRoutes.filter((v,i,a)=>a.findIndex(t=>(t.path === v.path && t.name === v.name))===i)

fs.writeFileSync(outputFilePath, JSON.stringify(uniqueRoutes, null, 2));
